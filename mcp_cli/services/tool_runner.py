from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, NamedTuple

from mcp_cli.services.frontier import is_sensitive_tool
from mcp_cli.services.logging import get_logger
from mcp_cli.services.roots import RootsManager

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger("tool_runner")


class KaryaEvent(NamedTuple):
    name: str
    args: dict[str, Any]
    result: str | None = None


def _mcp_tool_to_openai(tool: Any) -> dict[str, Any]:
    schema = tool.inputSchema or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


def _extract_text(result: Any) -> str:
    if result is None:
        return ""
    blocks = getattr(result, "content", None) or []
    parts = [getattr(b, "text", None) for b in blocks]
    return "\n".join(p for p in parts if p)


class ToolRunner:
    def __init__(
        self,
        tools_by_name: dict[str, dict[str, Any]],
        tool_timeout: float = 30.0,
        roots_manager: RootsManager | None = None,
        max_concurrent: int = 4,
    ):
        self.tools_by_name = tools_by_name
        self._tool_timeout = tool_timeout
        self.roots = roots_manager or RootsManager()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        entry = self.tools_by_name.get(name)
        if entry is None:
            return f"Unknown tool: {name}"

        root_err = self.roots.inspect_tool_args(name, args)
        if root_err:
            logger.warning("Root restriction on '%s': %s", name, root_err)
            return root_err

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    entry["client"].call_tool(name, args),
                    timeout=self._tool_timeout,
                )
                return _extract_text(result)
            except TimeoutError:
                return f"[timeout] Tool '{name}' did not respond within {self._tool_timeout}s"
            except Exception as exc:
                return f"Tool error: {exc}"

    async def execute_tool_calls(
        self,
        tool_calls: list[Any],
        *,
        on_tool_event: Callable[[KaryaEvent], None] | None = None,
        on_approval: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None,
    ) -> list[dict[str, Any]]:
        tool_results: list[dict[str, Any]] = []
        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if on_tool_event:
                on_tool_event(KaryaEvent(name=name, args=args))
            if on_approval and is_sensitive_tool(name):
                approved = await on_approval(name, args)
                if not approved:
                    result_text = f"[denied] Tool '{name}' was rejected by user"
                    if on_tool_event:
                        on_tool_event(KaryaEvent(name=name, args=args, result=result_text))
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": f"<tool_result name=\"{name}\">\n{result_text}\n</tool_result>",
                    })
                    continue
            result_text = await self.call_tool(name, args)
            if on_tool_event:
                on_tool_event(KaryaEvent(name=name, args=args, result=result_text))
            tool_results.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": f"<tool_result name=\"{name}\">\n{result_text}\n</tool_result>",
            })
        return tool_results
