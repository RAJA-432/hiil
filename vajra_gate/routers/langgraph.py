from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from vajra_gate.auth import get_current_user
from vajra_gate.chat import _require_chat
from vajra_gate.models import (
    RunWaitRequest,
    RunWaitResponse,
    ServerInfoResponse,
    StatelessRunRequest,
    StatelessRunResponse,
    StoreDeleteRequest,
    StoreGetRequest,
    StoreGetResponse,
    StoreItem,
    StoreSearchRequest,
    StoreSearchResponse,
    StoreUpsertRequest,
    ThreadCreateRequest,
    ThreadCreateResponse,
    ThreadItem,
    ThreadListResponse,
    ThreadRunRequest,
    ThreadRunResponse,
    ThreadSearchRequest,
)
from vajra_gate.store import get_store

router = APIRouter()

_START_TIME = time.time()

# ---------------------------------------------------------------------------
# /ok — simple health check
# ---------------------------------------------------------------------------


@router.get("/ok")
async def ok():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /info — server metadata
# ---------------------------------------------------------------------------


@router.get("/info", response_model=ServerInfoResponse)
async def info():
    return ServerInfoResponse(
        name="hiil",
        version="0.2.0",
        description="Conversational AI gateway with LangGraph-compatible API",
        endpoints=[
            "/ok", "/info",
            "/threads", "/threads/{thread_id}",
            "/threads/{thread_id}/runs",
            "/threads/{thread_id}/runs/stream",
            "/threads/{thread_id}/runs/wait",
            "/runs",
            "/store/items",
            "/store/items/search",
        ],
        langgraph_compat=True,
    )


# ---------------------------------------------------------------------------
# /threads — LangGraph-compatible thread management
# ---------------------------------------------------------------------------


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(request: Request, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sids = await chat.history.async_list_sessions()
    threads = []
    for sid in sids:
        msgs = await chat.history.async_load_session(sid)
        from vajra_gate.routers.sessions import _parse_session_ts
        created = _parse_session_ts(sid)
        created_at = created.isoformat() if created else sid
        threads.append(ThreadItem(
            thread_id=sid,
            created_at=created_at,
            updated_at=created_at,
            message_count=len(msgs),
        ))
    threads.sort(key=lambda t: t.created_at, reverse=True)
    return ThreadListResponse(threads=threads)


@router.post("/threads", response_model=ThreadCreateResponse)
async def create_thread(request: Request, body: ThreadCreateRequest | None = None, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    sid = chat.new_session()
    if body and body.metadata:
        await chat.history.async_rename_session(sid, str(body.metadata))
    return ThreadCreateResponse(thread_id=sid)


@router.get("/threads/{thread_id}", response_model=ThreadItem)
async def get_thread(request: Request, thread_id: str, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(thread_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    from vajra_gate.routers.sessions import _parse_session_ts
    created = _parse_session_ts(thread_id)
    created_at = created.isoformat() if created else thread_id
    return ThreadItem(
        thread_id=thread_id,
        created_at=created_at,
        updated_at=created_at,
        message_count=len(msgs),
    )


@router.post("/threads/{thread_id}/runs", response_model=ThreadRunResponse)
async def run_thread(request: Request, thread_id: str, body: ThreadRunRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(thread_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    chat.session_id = thread_id
    chat.messages = msgs

    user_input = body.input.get("messages", "")
    if not user_input:
        raise HTTPException(status_code=400, detail="input.messages required")

    result = await chat.send(user_input)
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    return ThreadRunResponse(
        run_id=run_id,
        thread_id=thread_id,
        status="completed",
        output={"reply": result},
    )


# ---------------------------------------------------------------------------
# /threads/{thread_id}/runs/stream — SSE streaming
# ---------------------------------------------------------------------------


@router.post("/threads/{thread_id}/runs/stream")
async def run_thread_stream(
    request: Request, thread_id: str, body: ThreadRunRequest,
    user: str = Depends(get_current_user),
):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(thread_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    chat.session_id = thread_id
    chat.messages = msgs
    user_input = body.input.get("messages", "")
    if not user_input:
        raise HTTPException(status_code=400, detail="input.messages required")

    run_id = f"run_{uuid.uuid4().hex[:12]}"

    async def _stream():
        bus: Any = None
        try:
            from mcp_cli.services.notification_bus import NotificationBus
            bus = NotificationBus()

            yield json.dumps({"event": "metadata", "data": {"run_id": run_id, "thread_id": thread_id}}) + "\n"

            full_reply = ""

            def on_chunk(chunk: str):
                nonlocal full_reply
                full_reply += chunk

            async def _run():
                await chat.send(user_input, notification_bus=bus, on_chunk=on_chunk)

            task = asyncio.create_task(_run())

            async for event in bus.events():
                yield json.dumps({"event": event.get("type", "message"), "data": event}) + "\n"

            await task

            yield json.dumps({
                "event": "complete",
                "data": {"run_id": run_id, "reply": full_reply},
            }) + "\n"

        except Exception as exc:
            yield json.dumps({"event": "error", "data": {"error": str(exc)}}) + "\n"
        finally:
            if bus:
                while bus._queues:
                    q = bus._queues.pop()
                    while not q.empty():
                        q.get_nowait()

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# /threads/{thread_id}/runs/wait — blocking wait with full response
# ---------------------------------------------------------------------------


@router.post("/threads/{thread_id}/runs/wait", response_model=RunWaitResponse)
async def run_thread_wait(
    request: Request, thread_id: str, body: RunWaitRequest,
    user: str = Depends(get_current_user),
):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(thread_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    chat.session_id = thread_id
    chat.messages = msgs
    user_input = body.input.get("messages", "")
    if not user_input:
        raise HTTPException(status_code=400, detail="input.messages required")

    bus: Any = None
    events: list[dict] = []
    try:
        from mcp_cli.services.notification_bus import NotificationBus
        bus = NotificationBus()
        async for event in bus.events():
            events.append(event)

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        result = await chat.send(user_input, notification_bus=bus)
        return RunWaitResponse(
            run_id=run_id,
            thread_id=thread_id,
            status="completed",
            output={"reply": result},
            events=events,
        )
    except Exception as exc:
        return RunWaitResponse(
            run_id=run_id or f"run_{uuid.uuid4().hex[:12]}",
            thread_id=thread_id,
            status="failed",
            output={"error": str(exc)},
            events=events,
        )
    finally:
        if bus:
            while bus._queues:
                q = bus._queues.pop()
                while not q.empty():
                    q.get_nowait()


# ---------------------------------------------------------------------------
# /runs — stateless run (no thread persistence)
# ---------------------------------------------------------------------------


@router.post("/runs", response_model=StatelessRunResponse)
async def stateless_run(request: Request, body: StatelessRunRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    user_input = body.input.get("messages", "")
    if not user_input:
        raise HTTPException(status_code=400, detail="input.messages required")

    current_sid = chat.session_id
    current_msgs = list(chat.messages)

    try:
        chat.new_session()
        result = await chat.send(user_input)
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        return StatelessRunResponse(
            run_id=run_id,
            output={"reply": result},
        )
    finally:
        chat.session_id = current_sid
        chat.messages = current_msgs


# ---------------------------------------------------------------------------
# /threads/{thread_id}/search — semantic search within thread
# ---------------------------------------------------------------------------


@router.post("/threads/{thread_id}/search")
async def search_thread(request: Request, thread_id: str, body: ThreadSearchRequest, user: str = Depends(get_current_user)):
    chat = await _require_chat(request)
    msgs = await chat.history.async_load_session(thread_id)
    if msgs is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    try:
        results = await chat.semantic_search(body.query, namespace=thread_id, limit=body.top_k)
    except NotImplementedError:
        results = []
    except Exception:
        results = []
        for m in msgs:
            score = 1.0 if body.query.lower() in (m.get("content", "") or "").lower() else 0.0
            if score > 0:
                results.append({"message": m, "score": score})
        results = sorted(results, key=lambda r: r["score"], reverse=True)[:body.top_k]

    return {"results": results, "count": len(results), "thread_id": thread_id}


# ---------------------------------------------------------------------------
# /store/items — LangGraph Store KV
# ---------------------------------------------------------------------------


@router.put("/store/items")
async def store_upsert(body: StoreUpsertRequest, user: str = Depends(get_current_user)):
    store = get_store()
    items = [item.model_dump() for item in body.items]
    store.upsert(body.namespace, items)
    return {"status": "ok", "namespace": body.namespace, "count": len(items)}


@router.get("/store/items", response_model=StoreGetResponse)
async def store_get(namespace: str = "default", keys: str = "", user: str = Depends(get_current_user)):
    store = get_store()
    key_list = [k.strip() for k in keys.split(",") if k.strip()]
    if not key_list:
        raise HTTPException(status_code=400, detail="keys query parameter required (comma-separated)")
    items = store.get_many(namespace, key_list)
    return StoreGetResponse(items=[
        StoreItem(**item) for item in items
    ])


@router.post("/store/items/query", response_model=StoreGetResponse)
async def store_get_post(body: StoreGetRequest, user: str = Depends(get_current_user)):
    store = get_store()
    items = store.get_many(body.namespace, body.keys)
    return StoreGetResponse(items=[
        StoreItem(**item) for item in items
    ])


@router.delete("/store/items")
async def store_delete(body: StoreDeleteRequest, user: str = Depends(get_current_user)):
    store = get_store()
    deleted = store.delete(body.namespace, body.keys)
    return {"status": "ok", "deleted": deleted, "namespace": body.namespace}


@router.post("/store/items/search", response_model=StoreSearchResponse)
async def store_search(body: StoreSearchRequest, user: str = Depends(get_current_user)):
    store = get_store()
    items = store.search(body.namespace, body.filter or {}, limit=body.limit)
    return StoreSearchResponse(
        items=[StoreItem(**item) for item in items],
        count=len(items),
    )
