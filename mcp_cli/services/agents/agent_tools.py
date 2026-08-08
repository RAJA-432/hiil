from __future__ import annotations

from typing import Any

from mcp_cli.services.agents.middleware.base import MiddlewarePipeline
from mcp_cli.services.tool_router import ToolRouter


class AgentTools:
    """Builds the OpenAI tool schema and formats tool results for the agent."""

    def __init__(self, tool_router: ToolRouter, middleware: MiddlewarePipeline | None) -> None:
        self._tool_router = tool_router
        self._middleware = middleware

    def _agent_tools(self) -> list[dict[str, Any]] | None:
        """Merge MCP tools with middleware extra tools."""
        tools = list(self._tool_router.openai_tools or [])
        if self._middleware:
            tools.extend(self._middleware.get_extra_tools())
        return tools or None

    @staticmethod
    def _has_delegate_tool(tool_calls: list[Any]) -> bool:
        for call in tool_calls:
            fn = getattr(call, "function", None)
            name = getattr(fn, "name", None)
            if name in ("delegate_task", "delegate_parallel"):
                return True
        return False

    @staticmethod
    def _tool_result(call: Any, name: str, content: str, raw: bool = False) -> dict[str, Any]:
        if raw:
            return {"role": "tool", "tool_call_id": call.id, "content": content}
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "content": f"<tool_result name=\"{name}\">\n{content}\n</tool_result>",
        }

    @staticmethod
    def _normalize_message(message: Any) -> dict[str, Any]:
        if hasattr(message, "model_dump"):
            return message.model_dump(exclude_unset=True)
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": getattr(message, "content", "") or "",
        }
        if hasattr(message, "tool_calls") and message.tool_calls:
            msg["tool_calls"] = message.tool_calls
        return msg
