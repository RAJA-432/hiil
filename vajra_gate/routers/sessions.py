import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat

router = APIRouter()

_SESSION_ID_TS = re.compile(r"session_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})")


def _parse_session_ts(sid: str) -> datetime | None:
    m = _SESSION_ID_TS.match(sid)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]), tzinfo=UTC)
        except ValueError:
            return None
    return None


@router.get("/api/sessions")
async def list_sessions(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sessions = await chat.history.async_list_sessions()
    return {"sessions": sessions, "active": chat.session_id}


@router.get("/api/conversations")
async def list_conversations(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sids = await chat.history.async_list_sessions()
    convs = []
    for sid in sids:
        created = _parse_session_ts(sid)
        msgs = await chat.history.async_load_session(sid)
        first = next((m for m in msgs if m.get("role") == "user"), None)
        title = first["content"][:80] if first else sid
        convs.append({
            "id": sid,
            "title": title,
            "created": created.isoformat() if created else sid,
            "updated": created.isoformat() if created else sid,
            "message_count": len(msgs),
        })
    convs.sort(key=lambda c: c["created"], reverse=True)
    return {"conversations": convs}


@router.get("/api/history/{session_id}")
async def get_history(request: Request, session_id: str, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(session_id)
    return {"messages": msgs}


@router.post("/api/session/new")
async def new_session(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sid = chat.new_session()
    return {"session_id": sid}


@router.post("/api/session/switch")
async def switch_session(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    body = await request.json()
    sid = body.get("session_id", "")
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    msgs = await chat.history.async_load_session(sid)
    chat.session_id = sid
    chat.messages = msgs
    return {"session_id": sid, "messages": len(msgs)}


@router.post("/api/session/rename")
async def rename_session(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    body = await request.json()
    session_id = body.get("session_id") or body.get("old_id", "")
    new_title = body.get("new_title") or body.get("new_id", "")
    if not session_id or not new_title:
        raise HTTPException(status_code=400, detail="session_id/old_id and new_title/new_id required")
    ok = await chat.history.async_rename_session(session_id, new_title)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": new_title}


@router.post("/api/session/delete")
async def delete_session(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    body = await request.json()
    sid = body.get("session_id", "")
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    await chat.history.async_delete_session(sid)
    return {"deleted": sid}
