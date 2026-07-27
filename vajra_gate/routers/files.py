import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from vajra_gate.config import WORKSPACE_DIR

logger = logging.getLogger("vajra_gate")

router = APIRouter()


def _safe_resolve(path: str) -> str:
    resolved = os.path.realpath(os.path.join(WORKSPACE_DIR, path))
    if not resolved.startswith(os.path.realpath(WORKSPACE_DIR)):
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return resolved


@router.get("/api/files/{path:path}")
async def read_file(path: str):
    safe_path = _safe_resolve(path)
    if not os.path.isfile(safe_path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        stat = os.stat(safe_path)
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
async def list_directory(dir: str = Query(".", description="Directory path")):
    safe_path = _safe_resolve(dir)
    if not os.path.isdir(safe_path):
        raise HTTPException(status_code=404, detail="Directory not found")
    try:
        entries = sorted(os.listdir(safe_path), key=lambda x: (not os.path.isdir(os.path.join(safe_path, x)), x.lower()))
        items = []
        for name in entries:
            full = os.path.join(safe_path, name)
            stat = os.stat(full)
            is_dir = os.path.isdir(full)
            items.append({
                "name": name,
                "type": "dir" if is_dir else "file",
                "size": 0 if is_dir else stat.st_size,
            })
        return {"name": os.path.basename(safe_path) or dir, "type": "dir", "children": items}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
