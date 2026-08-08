from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from pathlib import Path

from mcp.server.fastmcp import Context

from veda_engine.config import WORKSPACE_ROOT
from veda_engine.tools.path_guard import is_safe_path, validate_path
from veda_engine.tools.shell_safety import _c, _deny_reason, _reader_result

_MAX_TIMEOUT = 60
_OUTPUT_CAP_BYTES = 65_536
_CHUNK_SIZE = 4_096


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
    if proc is None:
        return "[error] failed to launch command"

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
