from __future__ import annotations

from abc import ABC
from typing import Any


class AgentMiddleware(ABC):
    """Base class for agent middleware.

    Middleware hooks into the agent lifecycle to augment messages, inject
    tools, or intercept tool calls — mirroring deepagents' middleware
    concept (``CodeInterpreterMiddleware``, ``MemoryMiddleware``,
    ``SummarizationMiddleware``).
    """

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Called once before the agent starts its message loop.

        Override to inject system-prompt additions, memory content, etc.
        """
        return messages

    def get_extra_tools(self) -> list[dict[str, Any]]:
        """Return additional OpenAI-format tool definitions.

        These are merged into the agent's tool list alongside MCP tools.
        """
        return []

    async def handle_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        """Intercept a tool call.

        Returns ``(handled, result_text)``.  If ``handled`` is ``True``
        the result is injected directly and the normal MCP dispatch is
        skipped.
        """
        return (False, None)


class MiddlewarePipeline:
    """Runs a list of middleware in order through the agent lifecycle."""

    def __init__(self, middleware: list[AgentMiddleware]):
        self._middleware = list(middleware)

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for mw in self._middleware:
            messages = mw.before_run(messages)
        return messages

    def get_extra_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for mw in self._middleware:
            tools.extend(mw.get_extra_tools())
        return tools

    async def handle_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        for mw in self._middleware:
            handled, result = await mw.handle_tool(name, args)
            if handled:
                return (True, result)
        return (False, None)
