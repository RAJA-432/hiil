import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

import vajra_gate.state as _state
from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat
from vajra_gate.models import (
    ConversationItem,
    ConversationListResponse,
    HistoryResponse,
    SessionDeleteRequest,
    SessionDeleteResponse,
    SessionListResponse,
    SessionNewResponse,
    SessionRenameRequest,
    SessionRenameResponse,
    SessionSwitchRequest,
    SessionSwitchResponse,
)

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


async def _session_exists(chat, session_id: str) -> bool:
    """Return True when a session id exists in history or is a live pool entry.

    ``async_load_session`` returns ``[]`` for unknown sessions, so it cannot be
    used to distinguish "empty session" from "missing session".  The current
    chat's ``session_id`` counts as existing (a freshly created thread has no
    persisted messages yet).
    """
    if chat.session_id == session_id:
        return True
    sids = await chat.history.async_list_sessions()
    if session_id in sids:
        return True
    pool = _state._get_pool()
    return session_id in pool._entries


@router.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sids = await chat.history.async_list_sessions()
    return SessionListResponse(sessions=sids, active=chat.session_id)


@router.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    user: str = Depends(get_current_user),
):
    if limit < 0 or offset < 0:
        raise HTTPException(status_code=422, detail="limit and offset must be non-negative")
    limit = min(limit, 100)
    chat = await _require_chat(request)
    total = await chat.history.async_count_sessions()
    summaries = await chat.history.async_session_summaries(limit=limit, offset=offset)
    convs = []
    for s in summaries:
        sid = s["session_id"]
        created = _parse_session_ts(sid)
        convs.append(ConversationItem(
            id=sid,
            title=(s["title"] or "")[:80],
            created=created.isoformat() if created else sid,
            updated=s["last_ts"],
            message_count=s["message_count"],
        ))
    return ConversationListResponse(conversations=convs, total=total)


@router.get("/api/history/{session_id}", response_model=HistoryResponse)
async def get_history(request: Request, session_id: str, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(session_id)
    return HistoryResponse(messages=msgs)


@router.post("/api/session/new", response_model=SessionNewResponse)
async def new_session(request: Request, user: str = Depends(get_current_user)):
    await _require_chat(request)
    pool = _state._get_pool()
    sid = await pool.new_session()
    _state._chat = await pool.get(pool.active)
    return SessionNewResponse(session_id=sid)


@router.post("/api/session/switch", response_model=SessionSwitchResponse)
async def switch_session(request: Request, body: SessionSwitchRequest, user: str = Depends(get_current_user)):
    sid = body.session_id
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    chat = await _require_chat(request)
    if not await _session_exists(chat, sid):
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found")
    chat = await _require_chat(request, session_id=sid)
    msgs = await chat.history.async_load_session(sid)
    async with chat.lock:
        chat.session_id = sid
        chat.messages = msgs
    pool = _state._get_pool()
    await pool.set_active(sid)
    _state._chat = chat
    return SessionSwitchResponse(session_id=sid, messages=len(msgs))


@router.post("/api/session/rename", response_model=SessionRenameResponse)
async def rename_session(request: Request, body: SessionRenameRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    session_id = body.session_id
    new_title = body.new_title
    if not session_id or not new_title:
        raise HTTPException(status_code=400, detail="session_id and new_title required")
    ok = await chat.history.async_rename_session(session_id, new_title)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRenameResponse(session_id=session_id)


@router.post("/api/session/delete", response_model=SessionDeleteResponse)
async def delete_session(request: Request, body: SessionDeleteRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sid = body.session_id
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    if not await _session_exists(chat, sid):
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found")
    await chat.history.async_delete_session(sid)
    await _state._get_pool().evict(sid)
    return SessionDeleteResponse(deleted=sid)
