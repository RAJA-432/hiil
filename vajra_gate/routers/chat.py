import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat, _stream_chat
from vajra_gate.models import (
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ModelSetRequest,
    ModelSetResponse,
    ModelsResponse,
    StatusResponse,
    TokenUsage,
    ToolCallRequest,
    ToolCallResponse,
    ToolListResponse,
    UsageResponse,
)

_GLOBAL_CHAT_TIMEOUT = 300.0

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat_api(request: Request, body: ChatRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    accept = request.headers.get("Accept", "")
    if "text/event-stream" in accept or request.query_params.get("stream") == "1":
        return StreamingResponse(
            _stream_chat(chat, body.message, session_id=body.session_id, images=body.images),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    full_reply = ""
    def on_chunk(c: str):
        nonlocal full_reply
        full_reply += c
    reply = await asyncio.wait_for(
        chat.send(body.message, on_chunk=on_chunk, images=body.images), timeout=_GLOBAL_CHAT_TIMEOUT
    )
    return ChatResponse(reply=reply or full_reply)


@router.get("/api/models", response_model=ModelsResponse)
async def list_models(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    try:
        models_data = await chat.claude.list_models()
        models = [
            ModelInfo(id=m.get("id", ""), name=m.get("name", ""), provider=m.get("provider", "")) for m in models_data
        ]
        return ModelsResponse(models=models, active=chat.claude.model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/status", response_model=StatusResponse)
async def status(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    s = chat.get_status()
    return StatusResponse(
        session_id=s.get("session"),
        model=s.get("model"),
        message_count=s.get("messages", 0),
        tool_count=s.get("tools", 0),
    )


@router.post("/api/model", response_model=ModelSetResponse)
async def set_model(request: Request, body: ModelSetRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    if not body.model.strip():
        raise HTTPException(status_code=400, detail="model must be a non-empty string")
    chat.claude.model = body.model
    return ModelSetResponse(model=body.model)


@router.get("/api/usage", response_model=UsageResponse)
async def get_usage(request: Request, session_id: str | None = None, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    if session_id:
        session = await chat.usage.async_session_summary_for(session_id)
    else:
        session = chat.usage.session_summary()
    total = chat.usage.total_summary()
    return UsageResponse(
        session=TokenUsage(**session) if session else TokenUsage(),
        total=TokenUsage(**total) if total else TokenUsage(),
    )


@router.get("/api/tools", response_model=ToolListResponse)
async def list_tools(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    return ToolListResponse(tools=list(chat.tools_by_name.keys()))


@router.post("/api/tools/call", response_model=ToolCallResponse)
async def call_tool(request: Request, body: ToolCallRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    if not body.name:
        raise HTTPException(status_code=400, detail="Tool name is required")
    try:
        result = await chat.call_tool_by_name(body.name, body.arguments)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ToolCallResponse(result=result)



