"""Shell-command safety (delegated to the shared ``hiil_common`` logic).

Kept as a module so existing imports (``veda_engine.tools.shell_safety``)
keep working unchanged. The workspace root is resolved at call time from
``veda_engine.config`` so tests that monkeypatch ``config.WORKSPACE_ROOT``
take effect.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp.server.fastmcp import Context

from hiil_common.utils.shell_safety import deny_reason
from veda_engine import config

__all__ = ["_c", "_deny_reason", "_reader_result"]


class _NoopCtx:
    async def info(self, *a, **kw): pass
    async def warning(self, *a, **kw): pass
    async def error(self, *a, **kw): pass
    async def report_progress(self, *a, **kw): pass


def _c(ctx: Context | None):
    return ctx or _NoopCtx()


def _deny_reason(command: str, cwd: Path) -> str | None:
    return deny_reason(command, cwd, config.WORKSPACE_ROOT)


def _reader_result(task: asyncio.Task[tuple[bytes, bool]]) -> tuple[bytes, bool]:
    """Return a drained reader's output, or empty bytes if it never finished."""
    if task.done() and not task.cancelled():
        try:
            return task.result()
        except Exception:
            return b"", False
    return b"", False
