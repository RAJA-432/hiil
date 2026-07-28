from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

_log = logging.getLogger(__name__)


class NotificationBus:
    """Async pub-sub bus for MCP progress, log, and tool events.

    Each streaming request gets its own bus. Supports multiple subscribers —
    each call to ``events()`` creates an independent queue and all published
    events are broadcast to every subscriber.

    Events that arrive *before* any subscriber registers are buffered and
    replayed to the first subscriber.
    """

    def __init__(self, max_queue_size: int = 1000):
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._done = False
        self._buffer: list[dict[str, Any]] = []
        self._max_queue_size = max_queue_size

    def _broadcast(self, event: dict[str, Any]) -> None:
        if not self._queues:
            if len(self._buffer) < self._max_queue_size:
                self._buffer.append(event)
            else:
                _log.warning("NotificationBus buffer full (%s), dropping event %s", self._max_queue_size, event.get("type"))
            return
        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                _log.warning("NotificationBus subscriber queue full, dropping event %s", event.get("type"))

    async def push_log(self, level: str, message: str, source: str = "") -> None:
        self._broadcast({"type": "log", "level": level, "text": message, "source": source})

    async def push_progress(self, current: int, total: int, message: str = "") -> None:
        pct = round((current / total) * 100, 1) if total else 0
        self._broadcast({"type": "progress", "current": current, "total": total, "percent": pct, "text": message})

    async def push_tool_call(self, name: str, args: dict[str, Any], status: str, result: str = "") -> None:
        self._broadcast({"type": "tool_event", "tool": name, "status": status, "args": args, "result": result[:200] if result else ""})

    async def push_interrupt(self, action_requests: list[dict]) -> None:
        self._broadcast({"type": "interrupt", "action_requests": action_requests})

    async def push_tokens(self, text: str) -> None:
        self._broadcast({"type": "tokens", "text": text})

    def push_tokens_nowait(self, text: str) -> None:
        self._broadcast({"type": "tokens", "text": text})

    def push_tool_call_nowait(self, name: str, args: dict[str, Any], status: str, result: str = "") -> None:
        self._broadcast({"type": "tool_event", "tool": name, "status": status, "args": args, "result": result[:200] if result else ""})

    def push_rag(self, chunks: list[dict[str, Any]]) -> None:
        self._broadcast({"type": "rag_context", "chunks": chunks})

    async def push_done(self) -> None:
        self._done = True
        self._broadcast({"type": "done"})

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._max_queue_size)
        self._queues.append(queue)
        # Drain pre-subscriber buffer into this queue.
        buffer_had_done = any(e.get("type") == "done" for e in self._buffer)
        for event in self._buffer:
            queue.put_nowait(event)
        self._buffer.clear()
        # If done was signaled but not actually in the buffer (e.g.
        # push_done was called after subscribers already existed), inject
        # a synthetic done so this subscriber terminates.
        if self._done and not buffer_had_done:
            queue.put_nowait({"type": "done"})
        try:
            await asyncio.sleep(0)
            while True:
                event = await queue.get()
                yield event
                if event["type"] == "done":
                    break
        finally:
            self._queues.remove(queue)
