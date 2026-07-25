from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp import types
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    LoggingMessageNotificationParams,
)
from mcp.shared.context import RequestContext

from mcp_client import prompts, resources, tools
from mcp_client.connection import ManagedConnection


class MCPClient:
    """High-level MCP client wrapper with a flat public API.

    Supports transports:
    - ``"stdio"`` (default) — subprocess stdio
    - ``"sse"`` — HTTP+SSE at a given URL
    - ``"streamable-http"`` — Streamable HTTP at a given URL
    """

    def __init__(
        self,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict | None = None,
        *,
        transport: str = "stdio",
        url: str = "",
        roots: list[str] | None = None,
        sampling_callback: Callable[
            [RequestContext, CreateMessageRequestParams],
            CreateMessageResult,
        ] | None = None,
        logging_callback: Callable[[LoggingMessageNotificationParams], Any] | None = None,
    ):
        self._conn = ManagedConnection(
            command=command, args=args, env=env,
            transport=transport,
            url=url,
            roots=roots,
            sampling_callback=sampling_callback,
            logging_callback=logging_callback,
        )

    @property
    def script(self) -> str:
        return self._conn.script

    @property
    def transport(self) -> str:
        return self._conn._transport

    async def connect(self):
        await self._conn.connect()

    def session(self):
        return self._conn.session()

    async def cleanup(self):
        await self._conn.cleanup()

    async def list_tools(self) -> list[types.Tool]:
        return await tools.list_tools(self._conn.session())

    async def call_tool(
        self, tool_name: str, tool_input: dict
    ) -> types.CallToolResult | None:
        return await tools.call_tool(self._conn.session(), tool_name, tool_input)

    async def list_prompts(self) -> list[types.Prompt]:
        return await prompts.list_prompts(self._conn.session())

    async def get_prompt(self, prompt_name: str, args: dict[str, str]):
        return await prompts.get_prompt(self._conn.session(), prompt_name, args)

    async def list_resources(self) -> list[types.Resource]:
        return await resources.list_resources(self._conn.session())

    async def read_resource(self, uri: str) -> Any:
        return await resources.read_resource(self._conn.session(), uri)

    async def create_message(
        self,
        params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        """Request an LLM sampling from the connected server (server-initiated)."""
        return await self._conn.session().create_message(
            messages=params.messages,
            max_tokens=params.max_tokens,
            system_prompt=params.system_prompt,
            include_context=params.include_context,
            temperature=params.temperature,
            stop_sequences=params.stop_sequences,
            metadata=params.metadata,
            model_preferences=params.model_preferences,
        )

    async def __aenter__(self):
        await self._conn.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._conn.cleanup()
