import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

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


@router.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sids = await chat.history.async_list_sessions()
    return SessionListResponse(sessions=sids, active=chat.session_id)


@router.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sids = await chat.history.async_list_sessions()
    convs = []
    for sid in sids:
        created = _parse_session_ts(sid)
        msgs = await chat.history.async_load_session(sid)
        first = next((m for m in msgs if m.get("role") == "user"), None)
        title = first["content"][:80] if first else sid
        convs.append(ConversationItem(
            id=sid,
            title=title,
            created=created.isoformat() if created else sid,
            updated=created.isoformat() if created else sid,
            message_count=len(msgs),
        ))
    convs.sort(key=lambda c: c.created, reverse=True)
    return ConversationListResponse(conversations=convs)


@router.get("/api/history/{session_id}", response_model=HistoryResponse)
async def get_history(request: Request, session_id: str, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(session_id)
    return HistoryResponse(messages=msgs)


@router.post("/api/session/new", response_model=SessionNewResponse)
async def new_session(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sid = chat.new_session()
    return SessionNewResponse(session_id=sid)


@router.post("/api/session/switch", response_model=SessionSwitchResponse)
async def switch_session(request: Request, body: SessionSwitchRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sid = body.session_id
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    msgs = await chat.history.async_load_session(sid)
    chat.session_id = sid
    chat.messages = msgs
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
    return SessionRenameResponse(session_id=new_title)


@router.post("/api/session/delete", response_model=SessionDeleteResponse)
async def delete_session(request: Request, body: SessionDeleteRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sid = body.session_id
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    await chat.history.async_delete_session(sid)
    return SessionDeleteResponse(deleted=sid)
