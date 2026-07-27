from __future__ import annotations

import os
import re
from pathlib import Path

_SUSPICIOUS_PATTERNS = re.compile(
    r"[\x00-\x1f]"       # null bytes and control chars
    r"|^\\\\\?"          # UNC paths on Windows
    r"|^\\\\\.\\"        # \\.\ device paths on Windows
)

_INTERNAL_BACKTRACK = re.compile(r"(?:^|[/\\])\.\.[/\\]")


def canonicalize(path: str | Path) -> Path:
    raw = Path(path)
    if _SUSPICIOUS_PATTERNS.search(str(raw)):
        raise ValueError("Path contains control characters or device prefixes")
    resolved = raw.resolve(strict=False)
    if os.name == "nt":
        resolved = Path(str(resolved).lower())
    return resolved


def is_safe_path(requested: Path, root: Path) -> bool:
    r_canon = canonicalize(root)
    p_canon = canonicalize(requested)
    if _INTERNAL_BACKTRACK.search(str(requested)):
        return False
    try:
        p_canon.relative_to(r_canon)
    except ValueError:
        return False
    expanded = Path(os.path.realpath(requested))
    if os.name == "nt":
        expanded = Path(str(expanded).lower())
    try:
        expanded.relative_to(r_canon)
    except ValueError:
        return False
    return True


def safe_relative(requested: Path, root: Path) -> Path | None:
    r_canon = canonicalize(root)
    p_canon = canonicalize(requested)
    if _INTERNAL_BACKTRACK.search(str(requested)):
        return None
    try:
        return p_canon.relative_to(r_canon)
    except ValueError:
        return None


def validate_path(requested: str | Path, root: Path) -> str | None:
    try:
        requested_path = Path(requested)
        if _INTERNAL_BACKTRACK.search(str(requested_path)):
            return "Path contains upward traversal (..)"
        if not requested_path.is_absolute():
            requested_path = (root / requested_path).resolve()
        if not is_safe_path(requested_path, root):
            return f"Access denied: path is not within the workspace root"
        return None
    except (ValueError, OSError) as exc:
        return f"Path validation error: {exc}"
