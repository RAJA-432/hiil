from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, NamedTuple

from mcp_cli.services.discovery import DiscoveryTracker
from mcp_cli.services.frontier import is_sensitive_tool
from mcp_cli.services.logging import get_logger
from mcp_cli.services.moderation import sanitize_tool_result
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
    result = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }
    # Apply compression to reduce token bloat
    return compress_schema(result)


def _extract_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    blocks = getattr(result, "content", None) or []
    parts = [getattr(b, "text", None) for b in blocks]
    return "\n".join(p for p in parts if p)


def compress_schema(schema: dict) -> dict:
    """Strip verbose defaults and optional descriptions to reduce token bloat."""
    import copy
    s = copy.deepcopy(schema)
    # Strip verbose descriptions and optional fields
    def strip_properties(prop_dict: dict) -> dict:
        stripped = {}
        for key, value in prop_dict.items():
            if key == "description":
                # Skip verbose descriptions
                continue
            if key == "default":
                # Skip default values that bloat tokens
                continue
            if key == "required" and isinstance(value, list):
                # Keep required but don't duplicate it elsewhere
                stripped[key] = value
            elif not isinstance(value, dict) or "default" not in value.get("properties", {}):
                # Keep other properties but strip unnecessary nesting
                stripped[key] = value
        return stripped

    # Apply stripping to parameters
    if "parameters" in s and isinstance(s["parameters"], dict):
        if "properties" in s["parameters"]:
            s["parameters"]["properties"] = strip_properties(s["parameters"]["properties"])
            # Simplify required field if it's bulky
            if "required" in s["parameters"] and isinstance(s["parameters"]["required"], list):
                # Keep only key required keywords
                stripped_required = []
                for req in s["parameters"]["required"]:
                    # Don't include things like "format" unless it's critical
                    if req not in ['format', 'pattern'] or req == 'format':
                        stripped_required.append(req)
                s["parameters"]["required"] = stripped_required

    return s


class ToolRunner:
    def __init__(
        self,
        tools_by_name: dict[str, dict[str, Any]],
        tool_timeout: float = 30.0,
        roots_manager: RootsManager | None = None,
        max_concurrent: int = 4,
        sanitize_results: bool = True,
        discovery: DiscoveryTracker | None = None,
    ):
        self.tools_by_name = tools_by_name
        self._tool_timeout = tool_timeout
        self.roots = roots_manager or RootsManager()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._sanitize_results = sanitize_results
        self.discovery = discovery

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

    def _finalize_content(self, content: str) -> str:
        if self._sanitize_results:
            return sanitize_tool_result(content)
        return content

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
                logger.warning("ToolRunner: malformed JSON arguments for '%s': %s", name, call.function.arguments)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": self._finalize_content(f"<tool_result name=\"{name}\">\n[invalid-args] Failed to parse arguments for '{name}'.\nRaw input: {call.function.arguments}\n</tool_result>"),
                })
                continue
            if on_tool_event:
                on_tool_event(KaryaEvent(name=name, args=args))
            discovery_note: str | None = None
            if self.discovery:
                self.discovery.record(name, args)
                discovery_note = self.discovery.check(name, args)
                if discovery_note and self.discovery.mode == "block":
                    result_text = discovery_note
                    if on_tool_event:
                        on_tool_event(KaryaEvent(name=name, args=args, result=result_text))
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": self._finalize_content(f"<tool_result name=\"{name}\">\n{result_text}\n</tool_result>"),
                    })
                    continue
            if on_approval and is_sensitive_tool(name):
                approved = await on_approval(name, args)
                if not approved:
                    result_text = f"[denied] Tool '{name}' was rejected by user"
                    if on_tool_event:
                        on_tool_event(KaryaEvent(name=name, args=args, result=result_text))
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": self._finalize_content(f"<tool_result name=\"{name}\">\n{result_text}\n</tool_result>"),
                    })
                    continue
            result_text = await self.call_tool(name, args)
            if discovery_note:
                result_text = f"{discovery_note}\n{result_text}"
            if on_tool_event:
                on_tool_event(KaryaEvent(name=name, args=args, result=result_text))
            tool_results.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": self._finalize_content(f"<tool_result name=\"{name}\">\n{result_text}\n</tool_result>"),
            })
        return tool_results
