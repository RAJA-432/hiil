from __future__ import annotations

import asyncio
import fnmatch
import logging
import re
from pathlib import Path

from mcp.server.fastmcp import Context

from veda_engine.config import WORKSPACE_ROOT
from veda_engine.tools.path_guard import is_safe_path, validate_path

logger = logging.getLogger(__name__)

_MAX_DEPTH = 4


def _c(ctx: Context | None):
    return ctx or _NoopCtx()


class _NoopCtx:
    async def info(self, *a, **kw): pass
    async def warning(self, *a, **kw): pass
    async def error(self, *a, **kw): pass
    async def report_progress(self, *a, **kw): pass


async def _walk_files(max_depth: int = _MAX_DEPTH) -> list[Path]:
    """Return all files under ``WORKSPACE_ROOT`` up to *max_depth* levels deep."""
    root = WORKSPACE_ROOT
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if len(rel.parents) <= max_depth:
            out.append(path)
    return out


async def search_resources(query: str, ctx: Context | None = None) -> list[str]:
    """Search the current workspace for files whose names contain the query."""
    c = _c(ctx)
    await c.info(f"Searching resources matching '{query}'...")
    needle = query.lower()
    matches = []
    all_files = await _walk_files()
    total = len(all_files)
    for i, path in enumerate(all_files):
        if needle in path.name.lower():
            matches.append(str(path.relative_to(WORKSPACE_ROOT)))
        if i % 50 == 0:
            await c.report_progress(min(i + 1, total), total)
    await c.info(f"Found {len(matches)} matching resources")
    return matches[:50]


async def glob(pattern: str, ctx: Context | None = None) -> list[str]:
    """Find files matching a glob pattern (e.g. ``**/*.py``, ``src/**/*.ts``) relative to the workspace root."""
    c = _c(ctx)
    await c.info(f"Globbing pattern '{pattern}'...")
    matches = []
    all_files = await _walk_files()
    total = len(all_files)
    for i, path in enumerate(all_files):
        rel = str(path.relative_to(WORKSPACE_ROOT))
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
            matches.append(rel)
        if i % 100 == 0:
            await c.report_progress(min(i + 1, total), total)
    await c.info(f"Glob found {len(matches)} files")
    return matches[:200]


async def grep(pattern: str, glob_pattern: str = "*", ctx: Context | None = None) -> list[str]:
    """Search file contents for a regex pattern. Returns ``file:line:content`` for each match."""
    c = _c(ctx)
    await c.info(f"Grepping for '{pattern}' in {glob_pattern} files...")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        await c.error(f"Invalid regex: {exc}")
        return [f"Invalid regex: {exc}"]

    results: list[str] = []
    candidates: list[Path] = []
    for p in await _walk_files():
        rel = str(p.relative_to(WORKSPACE_ROOT))
        if fnmatch.fnmatch(rel, glob_pattern) or fnmatch.fnmatch(p.name, glob_pattern):
            candidates.append(p)
    total = len(candidates)
    await c.info(f"Scanning {total} files...")
    for i, path in enumerate(candidates):
        rel = str(path.relative_to(WORKSPACE_ROOT))
        try:
            text: str = await asyncio.to_thread(
                lambda: path.read_text("utf-8", errors="replace")
            )
            for line in text.splitlines():
                if compiled.search(line):
                    results.append(f"{rel}:{line}")
                    if len(results) >= 200:
                        await c.info("Found 200+ matches, truncating")
                        return results
        except Exception:
            logger.exception("Failed to read %s", rel)
        if i % 20 == 0:
            await c.report_progress(min(i + 1, total), total)
    await c.info(f"Grep found {len(results)} matches")
    return results


async def read_text_resource(path: str, ctx: Context | None = None) -> str:
    """Read a text file from the workspace."""
    c = _c(ctx)
    await c.info(f"Reading {path}...")

    err = validate_path(path, WORKSPACE_ROOT)
    if err:
        await c.error(f"Path traversal blocked: {path} ({err})")
        return "Access denied: path traversal not allowed"

    target = (WORKSPACE_ROOT / path).resolve()
    if not is_safe_path(target, WORKSPACE_ROOT):
        await c.error(f"Path traversal blocked after resolution: {path}")
        return "Access denied: path traversal not allowed"

    exists = await asyncio.to_thread(target.exists)
    is_file = await asyncio.to_thread(target.is_file) if exists else False
    if not exists or not is_file:
        await c.error(f"File not found: {path}")
        return f"Resource not found: {path}"
    try:
        content = await asyncio.to_thread(
            lambda: target.read_text(encoding="utf-8", errors="ignore")
        )
        await c.info(f"Read {len(content)} bytes")
        return content
    except Exception as exc:
        await c.error(f"Read failed: {exc}")
        return f"Unable to read file: {exc}"
