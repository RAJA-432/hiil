from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _init_chat, _require_chat
from vajra_gate.crons import get_scheduler
from vajra_gate.metrics import generate as generate_metrics
from vajra_gate.metrics import inc_agent_run, inc_chat
from vajra_gate.a2a import get_a2a_bus

logger = logging.getLogger("vajra_gate.phase_c")
router = APIRouter()

# ---------------------------------------------------------------------------
# /metrics — Prometheus-format metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(generate_metrics(), media_type="text/plain; version=0.0.4")


# ---------------------------------------------------------------------------
# /ws — WebSocket chat
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        chat = await _init_chat()
    except Exception as exc:
        await websocket.send_json({"event": "error", "data": {"message": f"Chat init failed: {exc}"}})
        await websocket.close()
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "data": {"message": "Invalid JSON"}})
                continue

            msg_type = data.get("type", "chat")
            if msg_type == "ping":
                await websocket.send_json({"event": "pong"})
                continue

            if msg_type != "chat":
                await websocket.send_json({"event": "error", "data": {"message": f"Unknown type: {msg_type}"}})
                continue

            user_input = data.get("message", "")
            if not user_input.strip():
                await websocket.send_json({"event": "error", "data": {"message": "Empty message"}})
                continue

            inc_chat()

            async def _stream():
                from mcp_cli.services.notification_bus import NotificationBus
                bus = NotificationBus()
                full_reply = ""

                def on_chunk(chunk: str):
                    nonlocal full_reply
                    full_reply += chunk
                    try:
                        asyncio.ensure_future(
                            websocket.send_json({
                                "event": "token",
                                "data": {"chunk": chunk, "full": full_reply},
                            })
                        )
                    except Exception:
                        pass

                async def _run():
                    try:
                        await chat.send(
                            user_input,
                            notification_bus=bus,
                            on_chunk=on_chunk,
                        )
                    except Exception as exc:
                        try:
                            await websocket.send_json({"event": "error", "data": {"message": str(exc)}})
                        except Exception:
                            pass

                task = asyncio.create_task(_run())
                try:
                    async for event in bus.events():
                        try:
                            await websocket.send_json({
                                "event": event.get("type", "bus_event"),
                                "data": event,
                            })
                        except Exception:
                            break
                    await task
                except Exception:
                    pass
                finally:
                    bus._queues.clear()
                    try:
                        await websocket.send_json({
                            "event": "complete",
                            "data": {"reply": full_reply},
                        })
                    except Exception:
                        pass

            await _stream()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as exc:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json({"event": "error", "data": {"message": str(exc)}})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# /crons — scheduled tasks
# ---------------------------------------------------------------------------


@router.post("/crons")
async def create_cron(
    request: Request,
    body: dict,
    user: str = Depends(get_current_user),
):
    scheduler = get_scheduler()
    schedule_seconds = body.get("schedule_seconds", 3600)
    task_input = body.get("task_input", "")
    thread_id = body.get("thread_id")
    agent_config = body.get("agent_config")

    if not task_input:
        raise HTTPException(status_code=400, detail="task_input required")
    if schedule_seconds < 10:
        raise HTTPException(status_code=400, detail="schedule_seconds must be >= 10")

    job = scheduler.add(schedule_seconds, task_input, thread_id, agent_config)
    await scheduler.start(_init_chat)
    return {"status": "created", "cron": job.to_dict()}


@router.get("/crons")
async def list_crons(user: str = Depends(get_current_user)):
    scheduler = get_scheduler()
    return {"crons": [j.to_dict() for j in scheduler.list_jobs()]}


@router.get("/crons/{job_id}")
async def get_cron(job_id: str, user: str = Depends(get_current_user)):
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Cron '{job_id}' not found")
    return {"cron": job.to_dict()}


@router.delete("/crons/{job_id}")
async def delete_cron(job_id: str, user: str = Depends(get_current_user)):
    scheduler = get_scheduler()
    ok = scheduler.remove(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Cron '{job_id}' not found")
    return {"status": "deleted", "cron_id": job_id}


# ---------------------------------------------------------------------------
# /mcp/tools — MCP-over-HTTP tool endpoints
# ---------------------------------------------------------------------------


_FAKE_TOOL_RESULTS: dict[str, str] = {}


@router.get("/mcp/tools")
async def mcp_list_tools():
    return {
        "tools": [
            {
                "name": "hiil_chat",
                "description": "Send a message to the hiil assistant",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "The message to send"},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "hiil_list_threads",
                "description": "List all conversation threads",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "hiil_get_thread",
                "description": "Get messages in a thread",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string", "description": "Thread ID"},
                    },
                    "required": ["thread_id"],
                },
            },
            {
                "name": "hiil_list_agents",
                "description": "List all spawned agents",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "hiil_create_agent",
                "description": "Create a new subagent",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "capabilities": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "role"],
                },
            },
            {
                "name": "hiil_run_agent",
                "description": "Run an agent with a task",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "task": {"type": "string"},
                    },
                    "required": ["agent_id", "task"],
                },
            },
        ],
        "transport": "rest",
    }


@router.post("/mcp/tools/{tool_name}")
async def mcp_call_tool(tool_name: str, request: Request, body: dict):
    chat = await _require_chat(request)

    if tool_name == "hiil_chat":
        inc_chat()
        message = body.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="message required")
        result = await chat.send(message)
        return {"result": result, "tool": tool_name}

    if tool_name == "hiil_list_threads":
        sids = await chat.history.async_list_sessions()
        return {"result": {"threads": sids}, "tool": tool_name}

    if tool_name == "hiil_get_thread":
        thread_id = body.get("thread_id", "")
        msgs = await chat.history.async_load_session(thread_id)
        if msgs is None:
            raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
        return {"result": {"thread_id": thread_id, "messages": msgs}, "tool": tool_name}

    if tool_name == "hiil_list_agents":
        agents = chat.list_agents()
        return {"result": {"agents": agents}, "tool": tool_name}

    if tool_name == "hiil_create_agent":
        from mcp_cli.services.agents import AgentConfig
        name = body.get("name", "")
        role = body.get("role", "")
        capabilities = body.get("capabilities", [])
        config = AgentConfig(name=name, role=role, capabilities=capabilities)
        runner = chat.spawn_agent(config)
        return {
            "result": {
                "agent_id": runner.agent_id,
                "name": config.name,
                "role": config.role,
                "status": runner.state.status,
            },
            "tool": tool_name,
        }

    if tool_name == "hiil_run_agent":
        inc_agent_run()
        agent_id = body.get("agent_id", "")
        task = body.get("task", "")
        runner = chat.get_agent(agent_id)
        if runner is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        result = await runner.run(task)
        return {
            "result": {
                "agent_id": agent_id,
                "status": result.status,
                "output": result.output[:500],
            },
            "tool": tool_name,
        }

    raise HTTPException(status_code=404, detail=f"Unknown tool '{tool_name}'")


# ---------------------------------------------------------------------------
# /a2a — Agent-to-Agent communication
# ---------------------------------------------------------------------------


@router.post("/a2a/agents")
async def a2a_register(body: dict, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    name = body.get("name", "")
    role = body.get("role", "")
    capabilities = body.get("capabilities", [])
    if not name or not role:
        raise HTTPException(status_code=400, detail="name and role required")
    agent = bus.register(name, role, capabilities)
    return {"status": "registered", "agent": agent.to_dict()}


@router.get("/a2a/agents")
async def a2a_discover(capability: str | None = None, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    agents = bus.discover(capability)
    return {"agents": [a.to_dict() for a in agents]}


@router.get("/a2a/agents/{agent_id}")
async def a2a_get_agent(agent_id: str, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    agent = bus.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"A2A agent '{agent_id}' not found")
    return {"agent": agent.to_dict()}


@router.delete("/a2a/agents/{agent_id}")
async def a2a_unregister(agent_id: str, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    ok = bus.unregister(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"A2A agent '{agent_id}' not found")
    return {"status": "unregistered", "agent_id": agent_id}


@router.post("/a2a/agents/{agent_id}/heartbeat")
async def a2a_heartbeat(agent_id: str, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    ok = bus.heartbeat(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"A2A agent '{agent_id}' not found")
    return {"status": "ok", "agent_id": agent_id}


@router.post("/a2a/messages")
async def a2a_send(body: dict, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    sender_id = body.get("sender_id", "")
    recipient_id = body.get("recipient_id", "")
    content = body.get("content", "")
    thread_id = body.get("thread_id")
    if not sender_id or not recipient_id or not content:
        raise HTTPException(status_code=400, detail="sender_id, recipient_id, and content required")
    if bus.get_agent(sender_id) is None:
        raise HTTPException(status_code=404, detail=f"Sender '{sender_id}' not registered")
    if bus.get_agent(recipient_id) is None:
        raise HTTPException(status_code=404, detail=f"Recipient '{recipient_id}' not registered")
    msg = bus.send(sender_id, recipient_id, content, thread_id)
    return {"status": "sent", "message": msg.to_dict()}


@router.get("/a2a/messages")
async def a2a_get_messages(
    agent_id: str = "",
    unread_only: bool = False,
    limit: int = 50,
    user: str = Depends(get_current_user),
):
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id query parameter required")
    bus = get_a2a_bus()
    msgs = bus.get_messages(agent_id, unread_only=unread_only, limit=limit)
    return {"messages": [m.to_dict() for m in msgs], "count": len(msgs)}


@router.post("/a2a/messages/{message_id}/read")
async def a2a_mark_read(message_id: str, user: str = Depends(get_current_user)):
    bus = get_a2a_bus()
    ok = bus.mark_read(message_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found")
    return {"status": "read", "message_id": message_id}
