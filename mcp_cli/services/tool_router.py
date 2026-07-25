from __future__ import annotations

import re
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger("tool_router")


class ToolRouter:
    """Maps agent capabilities to filtered tool views across MCP servers.

    Each ``AgentRunner`` gets its own ``ToolRouter`` instance, wrapping the
    parent ``CliChat``'s full tool registry.  The router enforces that an
    agent may only list and call tools whose *capability tag* matches the
    agent's allowlist.

    Capability tagging (two strategies, tried in order):

    1. **Explicit map** — ``ToolRouter(tool_capability_map={...})``
       overrides auto-detection.
    2. **Convention** — A tool's server ID is its default capability tag.
       Tools served by a server called ``"filesystem"`` are tagged
       ``"filesystem"``.  Additionally, if a tool name starts with one of
       the agent's allowed prefixes it is permitted even when the server
       tag doesn't match (useful for generic servers like ``"doc_server"``).

    Usage::

        router = ToolRouter(
            tools_by_name=parent_chat.tools_by_name,
            clients=parent_chat.clients,
            capabilities=["filesystem", "github"],
            tool_capability_map={"read_file": "filesystem"},  # optional
        )
        openai_tools = router.openai_tools             # filtered
        result = await router.call_tool("read_file", {})
    """

    def __init__(
        self,
        tools_by_name: dict[str, dict[str, Any]],
        clients: dict[str, Any],
        capabilities: list[str],
        tool_capability_map: dict[str, str] | None = None,
    ):
        self._tools_by_name = tools_by_name
        self._clients = clients
        self._capabilities = [c.lower() for c in capabilities]
        self._explicit_map = tool_capability_map or {}
        self._server_caps = self._build_server_cap_index()

        self._allowed: dict[str, dict[str, Any]] = {}
        self._rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def openai_tools(self) -> list[dict[str, Any]]:
        return [v["openai"] for v in self._allowed.values()]

    @property
    def tool_names(self) -> list[str]:
        return list(self._allowed.keys())

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        entry = self._allowed.get(name)
        if entry is None:
            return f"[denied] Tool '{name}' is not in this agent's capabilities ({', '.join(self._capabilities)})"
        return await entry["client"].call_tool(name, args)

    # ------------------------------------------------------------------
    # Capability resolution
    # ------------------------------------------------------------------

    def _build_server_cap_index(self) -> dict[str, set[str]]:
        """Map each server ID → set of inferred capability tags."""
        index: dict[str, set[str]] = {}
        for server_id, client in self._clients.items():
            tags = {server_id.lower()}
            script = getattr(client, "script", "") or ""
            parts = re.split(r"[/\\_-]", script.lower().replace(".py", "").replace(".js", ""))
            tags.update(p for p in parts if p and len(p) > 1)
            index[server_id] = tags
        if "doc_client" not in self._clients:
            index["doc_client"] = {"doc", "docs", "document"}
        return index

    def _tool_is_allowed(self, tool_name: str, server_id: str | None) -> bool:
        explicit = self._explicit_map.get(tool_name)
        if explicit:
            return explicit.lower() in self._capabilities

        tool_lower = tool_name.lower()

        for cap in self._capabilities:
            if tool_lower.startswith(cap.rstrip("s") + "_"):
                return True
            if tool_lower.startswith(cap.rstrip("s")):
                return True

        if server_id:
            server_tags = self._server_caps.get(server_id, set())
            if server_tags & set(self._capabilities):
                return True

        return False

    def _resolve_server_id(self, client: Any) -> str | None:
        for sid, c in self._clients.items():
            if c is client:
                return sid
        return None

    def _rebuild(self) -> None:
        self._allowed.clear()
        for tool_name, entry in self._tools_by_name.items():
            client = entry.get("client")
            server_id = self._resolve_server_id(client)
            if self._tool_is_allowed(tool_name, server_id):
                self._allowed[tool_name] = entry

    def refresh(self) -> None:
        self._server_caps = self._build_server_cap_index()
        self._rebuild()
        logger.debug(
            "ToolRouter: %d / %d tools allowed for capabilities %s",
            len(self._allowed), len(self._tools_by_name), self._capabilities,
        )
