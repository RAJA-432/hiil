from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import Context
from pydantic import Field

from veda_engine.tools.path_guard import is_safe_path

logger = logging.getLogger(__name__)


def _file_url_to_path(uri: str) -> Path:
    """Convert a ``file://`` URI to a local ``Path``."""
    path_str = uri.removeprefix("file://")
    if path_str.startswith("/") and len(path_str) > 2 and path_str[2] == ":":
        path_str = path_str[1:]
    return Path(path_str).resolve()


async def is_path_allowed(requested_path: Path, ctx: Context) -> bool:
    """Check whether *requested_path* falls within one of the server's roots.

    Calls ``ctx.session.list_roots()`` to discover approved root directories
    from the client, then verifies the path is within one of them.
    """
    if not requested_path.exists():
        return False

    check = requested_path if requested_path.is_dir() else requested_path.parent

    try:
        roots_result = await ctx.session.list_roots()
    except Exception:
        logger.warning("list_roots failed, allowing access")
        return True

    for root in roots_result.roots:
        root_path = _file_url_to_path(str(root.uri))
        if is_safe_path(check, root_path):
            return True

    return False


async def list_roots(ctx: Context) -> list[str]:
    """List all directories that are accessible to this server.

    These are the root directories where files can be read from or written to.
    """
    try:
        roots_result = await ctx.session.list_roots()
        return [str(_file_url_to_path(str(r.uri))) for r in roots_result.roots]
    except Exception:
        logger.warning("list_roots failed, returning empty list")
        return []


async def read_dir(
    path: str = Field(description="Path to a directory to list"),
    *,
    ctx: Context,
) -> list[str]:
    """Read directory contents.  Path must be within one of the client's roots."""
    requested = Path(path).resolve()

    if not await is_path_allowed(requested, ctx):
        raise ValueError(
            f"Access denied: '{path}' is not within an approved root directory. "
            f"Use list_roots to see accessible directories."
        )

    if not requested.is_dir():
        raise ValueError(f"Not a directory: {path}")

    return sorted(
        str(p.relative_to(requested))
        if p.is_file()
        else str(p.relative_to(requested)) + "/"
        for p in requested.iterdir()
    )
