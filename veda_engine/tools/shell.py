from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess

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
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


async def run_command(
    command: str,
    cwd: str = ".",
    timeout: int = 30,
    ctx: Context | None = None,
) -> str:
    """Run a shell command inside the workspace root with sandbox guardrails.

    Commands matching ``_DENIED_PATTERNS`` are rejected before execution, ``cwd``
    is validated to stay inside ``WORKSPACE_ROOT``, the process tree is killed on
    timeout, and captured output is capped at ``_OUTPUT_CAP_BYTES``.
    """
    c = _c(ctx)
    command = command.strip()
    if not command:
        return "[denied] empty command"

    if _DENIED_PATTERNS.search(command):
        await c.warning(f"Command blocked by denylist: {command}")
        return "[denied] command matches a blocked pattern"

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

    await c.info(f"Running '{command}' in {target} with {timeout}s timeout")

    kwargs = {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "cwd": str(target),
        "env": {**os.environ, "PYTHONUNBUFFERED": "1"},
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    try:
        proc = await asyncio.create_subprocess_shell(command, **kwargs)  # noqa: S605
    except Exception as exc:
        await c.error(f"Failed to launch command: {exc}")
        return f"[error] failed to launch command: {exc}"

    readers = [
        asyncio.create_task(_drain(proc.stdout, _OUTPUT_CAP_BYTES)),
        asyncio.create_task(_drain(proc.stderr, _OUTPUT_CAP_BYTES)),
    ]
    try:
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            await _kill_process_tree(proc)
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                pass
            for task in readers:
                task.cancel()
            await c.error(f"Command timed out after {timeout}s")
            return f"[timeout] command exceeded {timeout}s and was killed"

        done, pending = await asyncio.wait(readers, timeout=timeout)
        for task in pending:
            task.cancel()
        if pending:
            out_bytes, out_truncated = b"", False
            err_bytes, err_truncated = b"", False
        else:
            out_bytes, out_truncated = readers[0].result()
            err_bytes, err_truncated = readers[1].result()
    except asyncio.CancelledError:
        for task in readers:
            task.cancel()
        await _kill_process_tree(proc)
        raise
    except Exception as exc:
        for task in readers:
            task.cancel()
        return f"[error] {exc}"

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
    if proc.returncode and proc.returncode != 0:
        parts.append(f"[exit code {proc.returncode}]")
    return "\n".join(parts) if parts else "(no output)"
