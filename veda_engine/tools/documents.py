from __future__ import annotations

import os
import re

from mcp.server.fastmcp import Context

from veda_engine.storage.store import edit_document as _edit
from veda_engine.storage.store import get_document


def _user_id(u: str) -> str:
    return u if u != "default" else os.environ.get("HIIL_USER_ID", "default")


def _c(ctx: Context | None):
    return ctx or _NoopCtx()


class _NoopCtx:
    async def info(self, *a, **kw): pass
    async def warning(self, *a, **kw): pass
    async def error(self, *a, **kw): pass


async def read_document(doc_id: str, user_id: str = "default", ctx: Context | None = None) -> str:
    """Read the contents of a document by ID."""
    c = _c(ctx)
    await c.info(f"Reading document '{doc_id}'...")
    content = get_document(doc_id, user_id=_user_id(user_id))
    if content:
        await c.info(f"Document '{doc_id}' loaded ({len(content)} chars)")
    else:
        await c.warning(f"Document '{doc_id}' not found")
    return content


async def edit_document(doc_id: str, old_str: str, new_str: str, user_id: str = "default", ctx: Context | None = None) -> str:
    """Edit a document by replacing the first occurrence of old_str with new_str."""
    c = _c(ctx)
    await c.info(f"Editing document '{doc_id}'...")
    result = _edit(doc_id, old_str, new_str, user_id=_user_id(user_id))
    await c.info(f"Document '{doc_id}' updated")
    return result


async def format_document(text: str, ctx: Context | None = None) -> str:
    """Normalise whitespace, remove trailing spaces, collapse blank lines, ensure final newline."""
    c = _c(ctx)
    await c.info("Formatting text...")
    lines = text.splitlines()
    cleaned = [line.rstrip() for line in lines]
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    if not result.endswith("\n"):
        result += "\n"
    await c.info(f"Formatted {len(lines)} lines -> {len(result)} chars")
    return result
