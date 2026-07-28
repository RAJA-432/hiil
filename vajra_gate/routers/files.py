import logging
import mimetypes
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from vajra_gate.config import WORKSPACE_DIR

logger = logging.getLogger("vajra_gate")

router = APIRouter()


def _safe_resolve(path: str) -> str:
    resolved = os.path.realpath(os.path.join(WORKSPACE_DIR, path))
    if not resolved.startswith(os.path.realpath(WORKSPACE_DIR)):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return resolved


def _rel_path(safe_path: str) -> str:
    return os.path.relpath(safe_path, WORKSPACE_DIR).replace(os.sep, "/")


def _build_tree(safe_path: str, max_depth: int = 5, depth: int = 0) -> dict:
    name = os.path.basename(safe_path) or safe_path
    if not os.path.isdir(safe_path):
        stat = os.stat(safe_path)
        return {"name": name, "type": "file", "path": _rel_path(safe_path), "size": stat.st_size}
    if depth >= max_depth:
        return {"name": name, "type": "dir", "path": _rel_path(safe_path), "children": []}
    try:
        entries = sorted(os.listdir(safe_path), key=lambda x: (not os.path.isdir(os.path.join(safe_path, x)), x.lower()))
    except PermissionError:
        return {"name": name, "type": "dir", "path": _rel_path(safe_path), "children": []}
    children = []
    for entry in entries:
        full = os.path.join(safe_path, entry)
        child = _build_tree(full, max_depth, depth + 1)
        children.append(child)
    return {"name": name, "type": "dir", "path": _rel_path(safe_path), "children": children}


@router.get("/api/files/{path:path}")
async def read_file(path: str):
    safe_path = _safe_resolve(path)
    if not os.path.isfile(safe_path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        stat = os.stat(safe_path)
        mime_type, _ = mimetypes.guess_type(safe_path)
        if mime_type and not mime_type.startswith("text/"):
            with open(safe_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type=mime_type or "application/octet-stream",
                headers={
                    "X-File-Path": path,
                    "X-File-Size": str(stat.st_size),
                    "X-File-MTime": str(datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()),
                },
            )
        with open(safe_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        return PlainTextResponse(
            content,
            headers={
                "X-File-Path": path,
                "X-File-Size": str(stat.st_size),
                "X-File-MTime": str(datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()),
            },
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


@router.get("/api/list")
async def list_directory(dir: str = Query(".", description="Directory path"), recursive: bool = Query(False, description="Return full recursive tree")):
    safe_path = _safe_resolve(dir)
    if not os.path.isdir(safe_path):
        raise HTTPException(status_code=404, detail="Directory not found")
    try:
        if recursive:
            return _build_tree(safe_path, max_depth=10)
        entries = sorted(os.listdir(safe_path), key=lambda x: (not os.path.isdir(os.path.join(safe_path, x)), x.lower()))
        items = []
        for name in entries:
            full = os.path.join(safe_path, name)
            stat = os.stat(full)
            is_dir = os.path.isdir(full)
            items.append({
                "name": name,
                "type": "dir" if is_dir else "file",
                "path": _rel_path(full),
                "size": 0 if is_dir else stat.st_size,
            })
        return {"name": os.path.basename(safe_path) or dir, "type": "dir", "path": _rel_path(safe_path), "children": items}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
