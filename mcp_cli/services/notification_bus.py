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
    """

    def __init__(self):
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._done = False

    def _broadcast(self, event: dict[str, Any]) -> None:
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

    async def push_done(self) -> None:
        self._done = True
        self._broadcast({"type": "done"})

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event["type"] == "done":
                    break
        finally:
            self._queues.remove(queue)
