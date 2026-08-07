import asyncio
import json
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from mcp_cli.services.agents import AgentConfig
from mcp_cli.services.agents.interrupts import DecisionType, ResumeDecision
from mcp_cli.services.notification_bus import NotificationBus
from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat
from vajra_gate.models import (
    AgentCreateResponse,
    AgentDetailResponse,
    AgentListResponse,
    AgentRouteRequest,
    AgentRouteResponse,
    AgentRunRequest,
    AgentStopResponse,
    ResumeRequest,
)

router = APIRouter()


async def _get_agent_or_404(request: Request, agent_id: str):
    chat = await _require_chat(request)
    runner = chat.get_agent(agent_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return chat, runner


@router.post("/api/agents", response_model=AgentCreateResponse)
async def create_agent(request: Request, body: AgentConfig, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    runner = chat.spawn_agent(body)
    return AgentCreateResponse(
        agent_id=runner.agent_id,
        name=runner.config.name,
        role=runner.config.role,
        capabilities=runner.config.capabilities,
        status=runner.state.status,
    )


@router.get("/api/agents", response_model=AgentListResponse)
async def list_agents(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    return AgentListResponse(agents=chat.list_agents())


@router.get("/api/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(request: Request, agent_id: str, user: str = Depends(get_current_user)):
    chat, runner = await _get_agent_or_404(request, agent_id)
    return AgentDetailResponse(
        agent_id=runner.agent_id,
        config=runner.config.model_dump(),
        state=runner.state.model_dump(),
        virtual_files=runner.virtual_files,
    )


@router.post("/api/agents/{agent_id}/route", response_model=AgentRouteResponse)
async def add_agent_route(request: Request, agent_id: str, body: AgentRouteRequest, user: str = Depends(get_current_user)):
    chat, runner = await _get_agent_or_404(request, agent_id)
    if not body.virtual_prefix or not body.real_path:
        raise HTTPException(status_code=400, detail="virtual_prefix and real_path required")
    runner.add_route(body.virtual_prefix, body.real_path)
    return AgentRouteResponse(status="route_added", virtual_prefix=body.virtual_prefix, real_path=body.real_path)


@router.post("/api/agents/{agent_id}/run")
async def run_agent(request: Request, agent_id: str, body: AgentRunRequest, user: str = Depends(get_current_user)):
    chat, runner = await _get_agent_or_404(request, agent_id)
    task_input = body.input
    if not task_input.strip():
        raise HTTPException(status_code=400, detail="input required")

    accept = request.headers.get("Accept", "")
    if "text/event-stream" in accept:
        bus = NotificationBus()
        runner.bus = bus

        async def event_stream():
            task: asyncio.Task | None = None
            try:
                async def execute():
                    try:
                        result = await runner.run(task_input)
                        if result.status == "waiting" and result.pending_interrupt:
                            await bus.push_interrupt([a.model_dump() for a in result.pending_interrupt])
                        else:
                            await bus.push_log("info", f"Agent completed: {result.output[:100]}...")
                    except asyncio.CancelledError:
                        pass
                    except Exception as exc:
                        await bus.push_log("error", str(exc))
                    finally:
                        await bus.push_done()

                task = asyncio.create_task(execute())
                async for event in bus.events():
                    yield json.dumps(event) + "\n"
            finally:
                if task is not None and not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, RuntimeError):
                        pass
                while bus._queues:
                    q = bus._queues.pop()
                    while not q.empty():
                        q.get_nowait()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await runner.run(task_input)
    return result.model_dump()


@router.post("/api/agents/{agent_id}/resume")
async def resume_agent(request: Request, agent_id: str, body: ResumeRequest, user: str = Depends(get_current_user)):
    chat, runner = await _get_agent_or_404(request, agent_id)
    if runner.state.status != "waiting":
        raise HTTPException(status_code=400, detail=f"Agent is not waiting (status: {runner.state.status})")
    if not body.decisions:
        raise HTTPException(status_code=400, detail="At least one decision required")

    decisions = [ResumeDecision(type=cast(DecisionType, d.type), edited_action=d.edited_action, message=d.message) for d in body.decisions]
    result = await runner.resume(decisions)
    return result.model_dump()


@router.post("/api/agents/{agent_id}/stop", response_model=AgentStopResponse)
async def stop_agent(request: Request, agent_id: str, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    ok = await chat.stop_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return AgentStopResponse(status="stopped")
