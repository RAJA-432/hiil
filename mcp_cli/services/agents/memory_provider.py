from __future__ import annotations

from typing import Any

from mcp_cli.services.agents.middleware.base import MiddlewarePipeline
from mcp_cli.services.agents.middleware.memory import MemoryMiddleware


class MemoryProvider:
    """Locates the long-term memory middleware and builds memory context blocks."""

    def __init__(self, middleware: MiddlewarePipeline | None) -> None:
        self._middleware = middleware

    def _find_memory_middleware(self) -> MemoryMiddleware | None:
        if self._middleware is None:
            return None
        for mw in self._middleware._middleware:
            if isinstance(mw, MemoryMiddleware):
                return mw
        return None

    def _memory_block_from_messages(
        self, messages: list[dict[str, Any]], mp: str,
    ) -> str | None:
        """Extract the current content of a memory file from the conversation.

        The injected memory block sits after the ``## Persistent Memory`` marker;
        the latest message carrying a copy of the block wins (e.g. the agent's
        final answer may carry an updated version of the file).
        """
        header = f"# Memory: {mp}"
        for msg in reversed(messages):
            content = msg.get("content", "")
            if not isinstance(content, str) or "## Persistent Memory" not in content:
                continue
            body = content.split("## Persistent Memory", 1)[1]
            for section in body.split("\n\n---\n"):
                lines = section.strip().splitlines()
                if lines and lines[0].strip() == header:
                    return "\n".join(lines[1:]).strip()
        return None
