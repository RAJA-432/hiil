from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Callable
from contextlib import AsyncExitStack
from typing import Any

from mcp.types import LoggingMessageNotificationParams

from mcp_cli.config import ServerConfig
from mcp_cli.services.logging import get_logger
from mcp_client import MCPClient

logger = get_logger("server_manager")

_SSE_BASE_PORT = int(os.getenv("MCP_SSE_BASE_PORT", "8100"))
_HTTP_BASE_PORT = int(os.getenv("MCP_HTTP_BASE_PORT", "8200"))
_DEFAULT_TRANSPORT = os.getenv("MCP_TRANSPORT", "sse")


def _find_free_port(start: int) -> int:
    """Return the first free port starting from *start*."""
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1


async def load_mcp_server(
    server_id: str,
    script: str,
    args: list[str] | None = None,
    env: dict[str, Any] | None = None,
    command: str | None = None,
    *,
    transport: str = "",
    roots: list[str] | None = None,
    sampling_callback: Callable | None = None,
    logging_callback: Callable[[LoggingMessageNotificationParams], Any] | None = None,
) -> MCPClient:
    """Launch and connect a new MCP server.

    When *transport* is ``"sse"`` the server is launched as an HTTP process on a
    free port and the client connects via SSE.  Otherwise stdio transport is used.
    """
    transport = transport or _DEFAULT_TRANSPORT
    cfg = ServerConfig(id=server_id, script=script, args=args or [],
                       env=env or {}, command=command)

    if transport == "sse":
        port = _find_free_port(_SSE_BASE_PORT)
        cmd, cmd_args = cfg.resolve_launch()
        sse_args = ["--transport", "sse", "--port", str(port)]
        client = MCPClient(
            command=cmd,
            args=[*cmd_args, *sse_args] if cmd_args else sse_args,
            env=env,
            transport="sse",
            url=f"http://127.0.0.1:{port}/sse",
            roots=roots,
            sampling_callback=sampling_callback,
            logging_callback=logging_callback,
        )
    elif transport == "streamable-http":
        port = _find_free_port(_HTTP_BASE_PORT)
        cmd, cmd_args = cfg.resolve_launch()
        http_args = ["--transport", "streamable-http", "--port", str(port)]
        client = MCPClient(
            command=cmd,
            args=[*cmd_args, *http_args] if cmd_args else http_args,
            env=env,
            transport="streamable-http",
            url=f"http://127.0.0.1:{port}/mcp",
            roots=roots,
            sampling_callback=sampling_callback,
            logging_callback=logging_callback,
        )
    else:
        cmd, cmd_args = cfg.resolve_launch()
        client = MCPClient(
            command=cmd,
            args=cmd_args,
            env=env,
            transport="stdio",
            roots=roots,
            sampling_callback=sampling_callback,
            logging_callback=logging_callback,
        )

    await asyncio.wait_for(client.connect(), timeout=30)
    return client


def _exc_message(exc: BaseException) -> str:
    """Return a short, readable message from a (possibly grouped) exception."""
    if isinstance(exc, BaseExceptionGroup):
        inner = exc.exceptions[0] if exc.exceptions else exc
        return _exc_message(inner)
    msg = str(exc)
    if not msg:
        return type(exc).__name__
    return msg.split("\n")[0][:200]


async def create_servers(
    servers_config: list[ServerConfig],
    stack: AsyncExitStack,
    *,
    transport: str = "",
    roots: list[str] | None = None,
    sampling_callback: Callable | None = None,
    logging_callback: Callable[[LoggingMessageNotificationParams], Any] | None = None,
) -> tuple[MCPClient | None, dict[str, MCPClient]]:
    """Start the doc server and all configured MCP servers.

    Returns ``(doc_client, clients)``.
    """
    transport = transport or _DEFAULT_TRANSPORT
    try:
        doc_client = await stack.enter_async_context(
            await load_mcp_server(
                "doc_server", "mcp_server",
                transport=transport,
                roots=roots,
                sampling_callback=sampling_callback,
                logging_callback=logging_callback,
            )
        )
    except Exception as exc:
        logger.warning("doc server: %s", _exc_message(exc))
        doc_client = None

    other_cfgs = [s for s in servers_config if s.script != "mcp_server"]

    async def _load_one(s_cfg: ServerConfig) -> tuple[str, MCPClient] | None:
        try:
            client = await stack.enter_async_context(
                await load_mcp_server(
                    s_cfg.id, s_cfg.script,
                    args=s_cfg.args,
                    env=s_cfg.env,
                    command=s_cfg.command,
                    transport=s_cfg.transport or transport,
                    roots=roots,
                    sampling_callback=sampling_callback,
                    logging_callback=logging_callback,
                )
            )
            return s_cfg.id, client
        except Exception as exc:
            logger.warning("%s: %s", s_cfg.id, _exc_message(exc))
            return None

    results = await asyncio.gather(*(
        _load_one(cfg) for cfg in other_cfgs
    ))
    clients = {}
    for r in results:
        if r is not None:
            cid, client = r
            clients[cid] = client

    return doc_client, clients
