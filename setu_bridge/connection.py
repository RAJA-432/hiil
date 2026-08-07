from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ListRootsResult,
    LoggingMessageNotificationParams,
    Root,
)
from pydantic import FileUrl

from setu_bridge.config import DEFAULT_CONNECT_TIMEOUT as _DEFAULT_CONNECT_TIMEOUT


class ManagedConnection:
    """Manages the transport context and session lifecycle for an MCP server.

    Supports transports:
    - ``"stdio"`` (default) — subprocess stdio
    - ``"sse"`` — HTTP+SSE at a given URL
    - ``"streamable-http"`` — Streamable HTTP at a given URL

    When *roots* are provided, the connection registers a
    ``list_roots_callback`` so that connected MCP servers can discover
    which directories they are allowed to access.

    When *sampling_callback* is provided, the server can request LLM
    inferences via the sampling protocol — the callback is invoked with
    ``CreateMessageRequestParams`` and must return ``CreateMessageResult``.
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
            [RequestContext[ClientSession, None], CreateMessageRequestParams],
            CreateMessageResult,
        ] | None = None,
        logging_callback: Callable[[LoggingMessageNotificationParams], Any] | None = None,
        connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
    ):
        self._command = command
        self._args = args or []
        self._env = env
        self._transport = transport
        self._url = url
        self._connect_timeout = connect_timeout
        self._roots = [Root(uri=FileUrl(f"file://{Path(p).resolve()}"), name=Path(p).name or "Root") for p in (roots or [])]
        self._sampling_callback = sampling_callback
        self._logging_callback = logging_callback
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self.script = command or ""
        if self._args:
            if "-m" in self._args:
                m_idx = self._args.index("-m")
                if m_idx + 1 < len(self._args):
                    self.script = self._args[m_idx + 1]
                else:
                    self.script = self._args[0]
            else:
                self.script = self._args[0]

    async def connect(self):
        try:
            if self._transport == "sse":
                await self._connect_sse()
            elif self._transport == "streamable-http":
                await self._connect_streamable_http()
            else:
                await self._connect_stdio()
        except BaseException:
            await self._exit_stack.aclose()
            self._session = None
            raise

    async def _handle_list_roots(
        self, context: RequestContext[ClientSession, None]
    ) -> ListRootsResult:
        """Callback invoked when the server requests the list of approved roots."""
        return ListRootsResult(roots=self._roots)

    def _session_args(self) -> dict:
        return dict(
            logging_callback=self._logging_callback,
            list_roots_callback=self._handle_list_roots if self._roots else None,
            sampling_callback=self._sampling_callback,
        )

    async def _connect_stdio(self):
        if self._command is None:
            raise RuntimeError("stdio transport requires a command")
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        streams = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        _read, _write = streams
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_read, _write, **self._session_args())
        )
        await asyncio.wait_for(self._session.initialize(), timeout=self._connect_timeout)

    async def _connect_sse(self):
        streams = await self._exit_stack.enter_async_context(
            sse_client(self._url)
        )
        _read, _write = streams
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_read, _write, **self._session_args())
        )
        await asyncio.wait_for(self._session.initialize(), timeout=self._connect_timeout)

    async def _connect_streamable_http(self):
        streams = await self._exit_stack.enter_async_context(
            streamable_http_client(self._url)
        )
        _read, _write, _get_session_id = streams
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_read, _write, **self._session_args())
        )
        await asyncio.wait_for(self._session.initialize(), timeout=self._connect_timeout)

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client session not initialized. Call connect() first."
            )
        return self._session

    async def cleanup(self):
        try:
            await self._exit_stack.aclose()
        except BaseException:
            pass
        self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
