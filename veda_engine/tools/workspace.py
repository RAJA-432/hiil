from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import re
from pathlib import Path

from mcp.server.fastmcp import Context

from veda_engine.config import WORKSPACE_ROOT
from veda_engine.tools.path_guard import is_safe_path, validate_path

logger = logging.getLogger(__name__)

_MAX_DEPTH = 4

_MAX_BATCH_FILES = 20
_MAX_FILE_BYTES = 100_000
_MAX_BATCH_BYTES = 500_000

_NOISE_DIRS = frozenset({
    ".git", ".venv", "venv", ".env", "node_modules", "__pycache__",
    ".egg-info", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".idea", ".vscode", "htmlcov", ".tox", ".eggs", "dist", "build",
})


def _read_bounded(path: Path, limit: int) -> str:
    """Read at most *limit* bytes from *path* and decode as UTF-8."""
    with open(path, "rb") as f:
        data = f.read(limit)
    return data.decode("utf-8", errors="ignore")


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
    visited: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dir_real = os.path.realpath(dirpath)
        if dir_real in visited:
            dirnames[:] = []
            continue
        visited.add(dir_real)
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth >= max_depth - 1:
            dirnames[:] = []
        else:
            dirnames[:] = [name for name in dirnames if name not in _NOISE_DIRS]
        if depth < max_depth:
            dir_abs = Path(dirpath)
            for name in filenames:
                out.append(dir_abs / name)
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
    if len(matches) > 50:
        return matches[:50] + ["[truncated: only first 50 matches shown]"]
    return matches


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
    if len(matches) > 200:
        return matches[:200] + ["[truncated: only first 200 matches shown]"]
    return matches


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
            resolved = await asyncio.to_thread(path.resolve)
            if not is_safe_path(resolved, WORKSPACE_ROOT):
                logger.warning("Skipping symlink escaping workspace: %s", rel)
                continue
            if not await asyncio.to_thread(resolved.is_file):
                logger.warning("Skipping non-regular file: %s", rel)
                continue
            text: str = await asyncio.to_thread(
                lambda: resolved.read_text("utf-8", errors="replace")
            )
            for lineno, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    results.append(f"{rel}:{lineno}:{line}")
                    if len(results) >= 200:
                        await c.info("Found 200+ matches, truncating")
                        return results + ["[truncated: only first 200 matches shown]"]
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
        size = (await asyncio.to_thread(target.stat)).st_size
        if size > _MAX_FILE_BYTES:
            content = await asyncio.to_thread(_read_bounded, target, _MAX_FILE_BYTES)
            await c.info(f"Read {len(content)} bytes (truncated from {size})")
            return content + f"\n[truncated at {_MAX_FILE_BYTES} bytes]"
        content = await asyncio.to_thread(
            lambda: target.read_text(encoding="utf-8", errors="ignore")
        )
        await c.info(f"Read {len(content)} bytes")
        return content
    except Exception as exc:
        await c.error(f"Read failed: {exc}")
        return f"Unable to read file: {exc}"


async def read_text_batch(paths: list[str], ctx: Context | None = None) -> str:
    """Read up to ``_MAX_BATCH_FILES`` workspace files concurrently into keyed blocks."""
    c = _c(ctx)
    await c.info(f"Reading {len(paths)} files in batch...")
    if not paths:
        return ""

    root = WORKSPACE_ROOT
    sem = asyncio.Semaphore(4)

    async def read_one(path: str) -> tuple[str, str, str]:
        err = validate_path(path, root)
        if err:
            await c.error(f"Path traversal blocked: {path} ({err})")
            return path, "denied", f"Access denied: {path} ({err})"

        target = (root / path).resolve()
        if not is_safe_path(target, root):
            await c.error(f"Path traversal blocked after resolution: {path}")
            return path, "denied", f"Access denied: {path} (path traversal not allowed)"

        async with sem:
            exists = await asyncio.to_thread(target.exists)
            is_file = await asyncio.to_thread(target.is_file) if exists else False
            if not exists or not is_file:
                await c.error(f"File not found: {path}")
                return path, "missing", f"Resource not found: {path}"
            try:
                size = (await asyncio.to_thread(target.stat)).st_size
                if size > _MAX_FILE_BYTES:
                    content = await asyncio.to_thread(_read_bounded, target, _MAX_FILE_BYTES)
                    content += f"\n[truncated at {_MAX_FILE_BYTES} bytes]"
                else:
                    content = await asyncio.to_thread(
                        lambda: target.read_text(encoding="utf-8", errors="ignore")
                    )
            except Exception as exc:
                await c.error(f"Read failed: {exc}")
                return path, "denied", f"Access denied: {path} ({exc})"
        await c.info(f"Read {len(content)} bytes from {path}")
        return path, "ok", content

    entries = await asyncio.gather(*(read_one(p) for p in paths[:_MAX_BATCH_FILES]))

    blocks: list[str] = []
    total_bytes = 0
    for path, kind, payload in entries:
        if kind in ("missing", "denied"):
            blocks.append(f"{payload}\n\n")
            continue
        block = f"=== {path} ===\n{payload}\n\n"
        if total_bytes + len(block) > _MAX_BATCH_BYTES:
            blocks.append(f"[batch truncated at {_MAX_BATCH_BYTES} bytes total]\n")
            break
        blocks.append(block)
        total_bytes += len(block)
    await c.info(f"Assembled {len(blocks)} blocks totaling {total_bytes} bytes")
    out = "".join(blocks)
    if len(paths) > _MAX_BATCH_FILES:
        out += f"[truncated: only first {_MAX_BATCH_FILES} of {len(paths)} files shown]\n"
    return out
