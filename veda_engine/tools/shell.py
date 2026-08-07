from __future__ import annotations

import asyncio
import os
import re
import shlex
import signal
import subprocess
from pathlib import Path

from mcp.server.fastmcp import Context

from veda_engine.config import WORKSPACE_ROOT
from veda_engine.tools.path_guard import is_safe_path, validate_path

_MAX_TIMEOUT = 60
_OUTPUT_CAP_BYTES = 65_536
_CHUNK_SIZE = 4_096

_DENIED_PATTERNS = re.compile(
    r"\brm\b[^|;&\n]*\s+-+[a-z]*r[a-z]*f[a-z]*\b[^|;&\n]*\s*[/\\*]"      # rm -rf /, rm -rf /*
    r"|\bmkfs\b"                                                            # filesystem creation
    r"|\bdd\b[^\n]*\bif="                                                   # dd if=<device> (disk wipe)
    r"|>\s*[/\\]dev[/\\]sd"                                                 # > /dev/sdX (disk overwrite)
    r"|\bformat\b\s+[a-zA-Z]:"                                              # format C:
    r"|:\(\)\s*\{|:[^\n]*\{\s*\|[^\n]*\}\s*&"                               # fork bombs
    r"|\b(shutdown|reboot|poweroff|halt|init)\b"
    r"|\bchmod\b[^\n]*\s+777\s+[/\\]"                                       # chmod 777 /
    r"|\b(curl|wget)\b[^\n]*\|\s*\bsh\b"                                    # curl|sh / wget|sh
    r"|\b(del|rd|rmdir)\b\s+[/\\]\s*s\b",                                   # del /s /f, rd /s /q
    re.IGNORECASE,
)

# Hard deny-by-verb list.  The command is tokenized with ``shlex`` and every
# token's executable name is checked against this list, so flags/targets are
# irrelevant: ``rm -rf /``, ``rd /q /s .`` and ``del /s *`` are all denied.
_DENIED_VERBS = frozenset({
    # File deletion / destruction
    "rm", "rmdir", "del", "erase", "rd", "deltree", "rdtree", "shred",
    # Disk / filesystem
    "format", "mkfs", "mkfs.ext4", "mkfs.btrfs", "mkswap", "wipefs",
    "fdisk", "parted", "sfdisk", "dd",
    # Power / reboot
    "shutdown", "reboot", "poweroff", "halt", "init", "telinit",
    # PowerShell destructive cmdlets
    "remove-item", "del-item", "clear-recyclebin",
})


def _executable_name(token: str) -> str:
    """Strip quotes, directory prefixes and extensions from a token."""
    name = token.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
        name = name[1:-1]
    name = name.split("/")[-1].split("\\")[-1].lower()
    for ext in (".exe", ".com", ".bat", ".cmd", ".ps1"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return name


def _separator_index(command: str) -> int:
    """Index of the first shell-level command separator, or -1.

    Quote-aware, so ``;``/``&``/``|`` inside quotes (e.g.
    ``python -c "a;b"``) are not treated as separators.
    """
    i, n, quote = 0, len(command), ""
    while i < n:
        ch = command[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch in ";&|\n":
            return i
        i += 1
    return -1


def _check_cd(tokens: list[str], cwd: Path) -> str | None:
    """Reject ``cd`` to absolute paths or targets that escape the workspace."""
    for i, tok in enumerate(tokens):
        if _executable_name(tok) != "cd":
            continue
        if i + 1 >= len(tokens):
            continue
        dest = tokens[i + 1].strip("\"'")
        if not dest:
            continue
        if Path(dest).is_absolute():
            return f"cd to absolute path '{dest}' is not allowed"
        if not is_safe_path((cwd / dest).resolve(), WORKSPACE_ROOT):
            return f"cd to '{dest}' escapes the workspace root"
    return None


def _check_redirects(command: str, cwd: Path) -> str | None:
    """Reject ``>``/``>>`` redirects whose target escapes the workspace root."""
    i, n, quote = 0, len(command), ""
    while i < n:
        ch = command[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch != ">":
            i += 1
            continue
        j = i + 1
        if j < n and command[j] == ">":
            j += 1
        while j < n and command[j] in " \t":
            j += 1
        target = ""
        q = ""
        while j < n:
            c2 = command[j]
            if q:
                target += c2
                if c2 == q:
                    q = ""
            elif c2 in "\"'":
                q = c2
                target += c2
            elif c2 in " \t;|&<>":
                break
            else:
                target += c2
            j += 1
        target = target.strip().strip("\"'")
        if target and (
            Path(target).is_absolute()
            or not is_safe_path((cwd / target).resolve(), WORKSPACE_ROOT)
        ):
            return f"redirect target '{target}' escapes the workspace root"
        i = j
    return None


def _deny_reason(command: str, cwd: Path) -> str | None:
    """Return a reason to deny *command*, or ``None`` if it may run."""
    if _DENIED_PATTERNS.search(command):
        return "command matches a blocked pattern"
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return "command has unbalanced quotes"
    for tok in tokens:
        if _executable_name(tok) in _DENIED_VERBS:
            return f"destructive command '{_executable_name(tok)}' is blocked"
    if _separator_index(command) != -1:
        return "command chaining/separators are not allowed"
    cd_err = _check_cd(tokens, cwd)
    if cd_err:
        return cd_err
    redirect_err = _check_redirects(command, cwd)
    if redirect_err:
        return redirect_err
    return None


class _NoopCtx:
    async def info(self, *a, **kw): pass
    async def warning(self, *a, **kw): pass
    async def error(self, *a, **kw): pass
    async def report_progress(self, *a, **kw): pass


def _c(ctx: Context | None):
    return ctx or _NoopCtx()


async def _drain(stream: asyncio.StreamReader, cap: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    truncated = False
    while True:
        chunk = await stream.read(_CHUNK_SIZE)
        if not chunk:
            break
        if total >= cap:
            truncated = True
            continue
        room = cap - total
        if len(chunk) > room:
            chunks.append(chunk[:room])
            total = cap
            truncated = True
        else:
            chunks.append(chunk)
            total += len(chunk)
    return b"".join(chunks), truncated


def _reader_result(task: asyncio.Task[tuple[bytes, bool]]) -> tuple[bytes, bool]:
    """Return a drained reader's output, or empty bytes if it never finished."""
    if task.done() and not task.cancelled():
        try:
            return task.result()
        except Exception:
            return b"", False
    return b"", False


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if os.name == "nt":
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/PID", str(proc.pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        except Exception:
            proc.kill()
    else:
        killpg = getattr(os, "killpg", None)
        getpgid = getattr(os, "getpgid", None)
        sigkill = getattr(signal, "SIGKILL", None)
        try:
            if killpg is None or getpgid is None or sigkill is None:
                proc.kill()
            else:
                killpg(getpgid(proc.pid), sigkill)
        except (ProcessLookupError, PermissionError):
            proc.kill()


async def _spawn(
    command: str,
    cwd: Path,
    env: dict[str, str],
    ctx: Context | None,
) -> tuple[asyncio.subprocess.Process | None, str | None]:
    """Create the subprocess; returns (proc, None) or (None, error message)."""
    c = _c(ctx)
    try:
        if os.name == "nt":
            proc = await asyncio.create_subprocess_shell(  # noqa: S605
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            proc = await asyncio.create_subprocess_shell(  # noqa: S605
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=env,
                start_new_session=True,
            )
    except Exception as exc:
        await c.error(f"Failed to launch command: {exc}")
        return None, f"[error] failed to launch command: {exc}"

    if proc.stdout is None or proc.stderr is None:
        await c.error("Failed to capture command output")
        proc.kill()
        await proc.wait()
        return None, "[error] failed to capture command output"

    return proc, None


async def _await_exit(proc: asyncio.subprocess.Process, timeout: int) -> bool:
    """Wait for exit, killing the process tree on timeout. Returns True if timed out."""
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except TimeoutError:
        await _kill_process_tree(proc)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            pass
        return True
    return False


async def _drain_outputs(
    proc: asyncio.subprocess.Process,
    timeout: int,
) -> tuple[bool, bytes, bool, bytes, bool]:
    """Wait for exit then collect stdout/stderr.

    Returns (timed_out, out_bytes, out_truncated, err_bytes, err_truncated).
    """
    stdout = proc.stdout
    stderr = proc.stderr
    if stdout is None or stderr is None:
        raise RuntimeError("subprocess output streams are unavailable")

    readers = [
        asyncio.create_task(_drain(stdout, _OUTPUT_CAP_BYTES)),
        asyncio.create_task(_drain(stderr, _OUTPUT_CAP_BYTES)),
    ]
    timed_out = False
    try:
        timed_out = await _await_exit(proc, timeout)

        done, pending = await asyncio.wait(readers, timeout=5)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        out_bytes, out_truncated = _reader_result(readers[0])
        err_bytes, err_truncated = _reader_result(readers[1])
        return timed_out, out_bytes, out_truncated, err_bytes, err_truncated
    except asyncio.CancelledError:
        for task in readers:
            task.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        raise
    except Exception:
        for task in readers:
            task.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        raise


def _format_output(
    out_bytes: bytes,
    out_truncated: bool,
    err_bytes: bytes,
    err_truncated: bool,
    returncode: int | None,
) -> str:
    """Assemble the final user-visible result string from captured output."""
    out = out_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
    err = err_bytes.decode("utf-8", errors="replace").rstrip("\r\n")

    trunc_marker = f"\n[output truncated at {_OUTPUT_CAP_BYTES} bytes]"
    parts: list[str] = []
    if out:
        parts.append(out)
        if out_truncated:
            parts.append(trunc_marker)
    if err:
        parts.append(f"[stderr]\n{err}")
        if err_truncated:
            parts.append(trunc_marker)
    if returncode and returncode != 0:
        parts.append(f"[exit code {returncode}]")
    return "\n".join(parts) if parts else "(no output)"


async def run_command(
    command: str,
    cwd: str = ".",
    timeout: int = 30,
    ctx: Context | None = None,
) -> str:
    """Run a shell command inside the workspace root.

    Commands are vetted with a deny-by-verb guard before execution: the command
    is tokenized with ``shlex`` and each token's executable name is checked
    against a hard deny-list of destructive commands (``rm``, ``del``, ``rd``,
    ``mkfs``, ``dd``, ``shutdown``, ...); command chaining via
    ``&&``/``||``/``;``/``|``/``&``/newlines is rejected; ``cd`` and
    ``>``/``>>`` redirect targets may not escape ``WORKSPACE_ROOT``. The legacy
    ``_DENIED_PATTERNS`` regex is kept as defense-in-depth. ``cwd`` is validated
    to stay inside ``WORKSPACE_ROOT``, the process tree is killed on timeout,
    and captured output is capped at ``_OUTPUT_CAP_BYTES``.
    """
    c = _c(ctx)
    command = command.strip()
    if not command:
        return "[denied] empty command"

    timeout = max(1, min(int(timeout), _MAX_TIMEOUT))

    path_err = validate_path(cwd, WORKSPACE_ROOT)
    if path_err:
        await c.error(f"cwd rejected: {cwd} ({path_err})")
        return "[denied] cwd must be inside the workspace root"
    target = (WORKSPACE_ROOT / cwd).resolve()
    if not is_safe_path(target, WORKSPACE_ROOT):
        await c.error(f"cwd rejected after resolution: {cwd}")
        return "[denied] cwd must be inside the workspace root"
    if not await asyncio.to_thread(target.is_dir):
        await c.error(f"cwd not found: {cwd}")
        return f"[error] cwd is not a directory: {cwd}"

    reason = _deny_reason(command, target)
    if reason:
        await c.warning(f"Command blocked: {command} ({reason})")
        return f"[denied] {reason}"

    await c.info(f"Running '{command}' in {target} with {timeout}s timeout")

    env: dict[str, str] = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc, spawn_err = await _spawn(command, target, env, ctx)
    if spawn_err:
        return spawn_err

    try:
        timed_out, out_bytes, out_truncated, err_bytes, err_truncated = (
            await _drain_outputs(proc, timeout)
        )
    except asyncio.CancelledError:
        await _kill_process_tree(proc)
        raise
    except Exception as exc:
        return f"[error] {exc}"

    if timed_out:
        await c.error(f"Command timed out after {timeout}s")
        return f"[timeout] command exceeded {timeout}s and was killed"

    return _format_output(out_bytes, out_truncated, err_bytes, err_truncated, proc.returncode)
