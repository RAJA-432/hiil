import logging
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from vajra_gate.config import WORKSPACE_DIR
from vajra_gate.models import (
    FileCreateDirRequest,
    FileDeleteRequest,
    FileItem,
    FileOperationResponse,
    FileRenameRequest,
    FileWriteRequest,
)
from vajra_gate.services.filesystem import FileSystem

logger = logging.getLogger("vajra_gate")

router = APIRouter()

fs = FileSystem(WORKSPACE_DIR)


def _to_fileitem(data: dict) -> FileItem:
    return FileItem(
        name=data["name"],
        type=data["type"],
        path=data["path"],
        size=data.get("size", 0),
        children=[_to_fileitem(c) for c in data["children"]] if data.get("children") else None,
    )


def _handle_fs_error(func):
    try:
        return func()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except IsADirectoryError:
        raise HTTPException(status_code=400, detail="Is a directory")
    except OSError as e:
        logger.exception("Filesystem error")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/files/{path:path}")
async def read_file(path: str):
    def _read():
        content, media_type, headers = fs.read_file(path)
        if isinstance(content, bytes):
            return Response(content=content, media_type=media_type or "application/octet-stream", headers=headers)
        return PlainTextResponse(content, headers=headers)
    return _handle_fs_error(_read)


@router.get("/api/list", response_model=FileItem)
async def list_directory(dir: str = Query(".", description="Directory path"), recursive: bool = Query(False, description="Return full recursive tree")):
    def _list():
        if recursive:
            data = fs.build_tree(dir, max_depth=10)
            if data is None:
                raise HTTPException(status_code=404, detail="Directory not found or ignored")
            return _to_fileitem(data)
        items = fs.list_dir(dir)
        safe = fs.resolve(dir)
        name = os.path.basename(safe) or dir
        return FileItem(name=name, type="dir", path=fs.relpath(safe), children=[_to_fileitem(i) for i in items])
    return _handle_fs_error(_list)


@router.put("/api/files", response_model=FileOperationResponse)
async def write_file(req: FileWriteRequest):
    def _write():
        path = fs.write_file(req.path, req.content)
        return FileOperationResponse(success=True, path=path, message="File written")
    return _handle_fs_error(_write)


@router.post("/api/dirs", response_model=FileOperationResponse)
async def create_directory(req: FileCreateDirRequest):
    def _mkdir():
        path = fs.create_dir(req.path)
        return FileOperationResponse(success=True, path=path, message="Directory created")
    return _handle_fs_error(_mkdir)


@router.delete("/api/files", response_model=FileOperationResponse)
async def delete_file(req: FileDeleteRequest):
    def _delete():
        path = fs.delete(req.path)
        return FileOperationResponse(success=True, path=path, message="Deleted")
    return _handle_fs_error(_delete)


@router.post("/api/files/rename", response_model=FileOperationResponse)
async def rename_file(req: FileRenameRequest):
    def _rename():
        new_path, old_path = fs.rename(req.path, req.new_path)
        return FileOperationResponse(success=True, path=new_path, message=f"Renamed from {old_path}")
    return _handle_fs_error(_rename)
