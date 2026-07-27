import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat, _stream_chat
from vajra_gate.models import ChatRequest, KaryaRequest

_GLOBAL_CHAT_TIMEOUT = 300.0

router = APIRouter()


@router.post("/api/chat")
async def chat_api(request: Request, body: ChatRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    accept = request.headers.get("Accept", "")
    if "text/event-stream" in accept or request.query_params.get("stream") == "1":
        return StreamingResponse(
            _stream_chat(chat, body.message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    full_reply = ""
    def on_chunk(c: str):
        nonlocal full_reply
        full_reply += c
    reply = await asyncio.wait_for(chat.send(body.message, on_chunk=on_chunk), timeout=_GLOBAL_CHAT_TIMEOUT)
    return {"reply": reply or full_reply}


@router.get("/api/models")
async def list_models(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    try:
        models = await chat.claude.list_models()
        return {"models": models, "active": chat.claude.model}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/status")
async def status(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    return chat.get_status()


@router.post("/api/model")
async def set_model(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    body = await request.json()
    model = body.get("model", "")
    if not model or not isinstance(model, str):
        raise HTTPException(status_code=400, detail="model must be a non-empty string")
    chat.claude.model = model
    return {"model": model}


@router.get("/api/usage")
async def get_usage(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    session = chat.usage.session_summary()
    total = chat.usage.total_summary()
    return {"session": session, "total": total}


@router.get("/api/tools")
async def list_tools(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    return {"tools": list(chat.tools_by_name.keys())}


@router.post("/api/tools/call")
async def call_tool_api(request: Request, body: KaryaRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    try:
        result = await chat.call_tool_by_name(body.name, body.arguments)
        return {"result": result}
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
