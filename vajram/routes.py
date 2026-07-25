
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from mcp_cli.services.agents import AgentConfig
from mcp_cli.services.agents.interrupts import ResumeDecision
from mcp_cli.services.notification_bus import NotificationBus
from vajram.chat import _require_chat, _stream_chat
from vajram.config import _CHAT_HTML
from vajram.models import ChatRequest, ToolCallRequest
from vajram.storage import HspStorage

router = APIRouter()
storage = HspStorage()


class ResumeRequest(BaseModel):
    decisions: list[ResumeDecision]


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and store it in the document store."""
    try:
        file_data = await file.read()
        doc_id = await storage.store_file(file_data, file.filename or "unknown")
        return {"doc_id": doc_id, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents")
async def list_documents():
    """List all stored documents."""
    return {"documents": storage.list_documents()}


@router.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document content by ID."""
    try:
        content = storage.get_document(doc_id)
        file_content = await storage.get_file_content(doc_id)
        return {
            "doc_id": doc_id,
            "content": content,
            "has_file": file_content is not None,
            "file_size": len(file_content) if file_content else 0
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/chat")
async def chat_api(request: Request, body: ChatRequest):
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
    reply = await chat.send(body.message, on_chunk=on_chunk)
    return {"reply": reply or full_reply}


@router.get("/api/models")
async def list_models(request: Request):
    chat = await _require_chat(request)
    try:
        models = await chat.claude.list_models()
        return {"models": models, "active": chat.claude.model}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/status")
async def status(request: Request):
    chat = await _require_chat(request)
    return chat.get_status()


@router.post("/api/model")
async def set_model(request: Request):
    chat = await _require_chat(request)
    body = await request.json()
    model = body.get("model", "")
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    chat.claude.model = model
    return {"model": model}


@router.get("/api/sessions")
async def list_sessions(request: Request):
    chat = await _require_chat(request)
    sessions = await chat.history.async_list_sessions()
    return {"sessions": sessions, "active": chat.session_id}


@router.get("/api/history/{session_id}")
async def get_history(request: Request, session_id: str):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(session_id)
    return {"messages": msgs}


@router.post("/api/session/new")
async def new_session(request: Request):
    chat = await _require_chat(request)
    sid = chat.new_session()
    return {"session_id": sid}


@router.post("/api/session/switch")
async def switch_session(request: Request):
    chat = await _require_chat(request)
    body = await request.json()
    sid = body.get("session_id", "")
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    msgs = await chat.history.async_load_session(sid)
    chat.session_id = sid
    chat.messages = msgs
    return {"session_id": sid, "messages": len(msgs)}


@router.get("/api/tools")
async def list_tools(request: Request):
    chat = await _require_chat(request)
    return {"tools": list(chat.tools_by_name.keys())}


@router.post("/api/tools/call")
async def call_tool_api(request: Request, body: ToolCallRequest):
    chat = await _require_chat(request)
    try:
        result = await chat.call_tool_by_name(body.name, body.arguments)
        return {"result": result}
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/hi")
async def hi():
    return "hi"


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/api/agents")
async def create_agent(request: Request, body: AgentConfig):
    chat = await _require_chat(request)
    runner = chat.spawn_agent(body)
    return {
        "agent_id": runner.agent_id,
        "name": runner.config.name,
        "role": runner.config.role,
        "capabilities": runner.config.capabilities,
        "status": runner.state.status,
    }


@router.get("/api/agents")
async def list_agents(request: Request):
    chat = await _require_chat(request)
    return {"agents": chat.list_agents()}


@router.get("/api/agents/{agent_id}")
async def get_agent(request: Request, agent_id: str):
    chat = await _require_chat(request)
    runner = chat.get_agent(agent_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {
        "agent_id": runner.agent_id,
        "config": runner.config.model_dump(),
        "state": runner.state.model_dump(),
        "virtual_files": runner.virtual_files,
    }


@router.post("/api/agents/{agent_id}/route")
async def add_agent_route(request: Request, agent_id: str):
    chat = await _require_chat(request)
    runner = chat.get_agent(agent_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    body = await request.json()
    virtual_prefix = body.get("virtual_prefix", "")
    real_path = body.get("real_path", "")
    if not virtual_prefix or not real_path:
        raise HTTPException(status_code=400, detail="virtual_prefix and real_path required")
    runner.add_route(virtual_prefix, real_path)
    return {"status": "route_added", "virtual_prefix": virtual_prefix, "real_path": real_path}


@router.post("/api/agents/{agent_id}/run")
async def run_agent(request: Request, agent_id: str):
    chat = await _require_chat(request)
    runner = chat.get_agent(agent_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    body = await request.json()
    task_input = body.get("input", "")
    if not task_input.strip():
        raise HTTPException(status_code=400, detail="input required")

    accept = request.headers.get("Accept", "")
    if "text/event-stream" in accept:
        bus = NotificationBus()
        runner.bus = bus
        async def event_stream():
            import asyncio
            import json
            async def execute():
                try:
                    result = await runner.run(task_input)
                    if result.status == "waiting" and result.pending_interrupt:
                        await bus.push_interrupt([a.model_dump() for a in result.pending_interrupt])
                    else:
                        await bus.push_log("info", f"Agent completed: {result.output[:100]}...")
                except Exception as exc:
                    await bus.push_log("error", str(exc))
                finally:
                    await bus.push_done()
            asyncio.create_task(execute())
            async for event in bus.events():
                yield json.dumps(event) + "\n"
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await runner.run(task_input)
    return result.model_dump()


@router.post("/api/agents/{agent_id}/resume")
async def resume_agent(request: Request, agent_id: str, body: ResumeRequest):
    chat = await _require_chat(request)
    runner = chat.get_agent(agent_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    if runner.state.status != "waiting":
        raise HTTPException(status_code=400, detail=f"Agent is not waiting (status: {runner.state.status})")
    if not body.decisions:
        raise HTTPException(status_code=400, detail="At least one decision required")

    result = await runner.resume(body.decisions)
    return result.model_dump()


@router.post("/api/agents/{agent_id}/stop")
async def stop_agent(request: Request, agent_id: str):
    chat = await _require_chat(request)
    ok = await chat.stop_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {"status": "stopped"}


@router.get("/chat", response_class=HTMLResponse)
async def chat_ui(request: Request):
    return HTMLResponse(_CHAT_HTML)
