from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import AsyncExitStack
from typing import Any

from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    TextContent,
)

from mcp_cli.config import load_settings
from mcp_cli.services.chat import CliChat
from mcp_cli.services.claude import Claude
from mcp_cli.services.logging import get_logger
from mcp_cli.services.roots import RootsManager
from mcp_cli.services.server_manager import create_servers

logger = get_logger("factory")


def _build_sampling_callback(
    claude: Claude,
) -> Callable[[RequestContext, CreateMessageRequestParams], Coroutine[Any, Any, CreateMessageResult]]:
    """Return a sampling callback that delegates LLM inference to the *claude* service."""

    async def _sample(
        context: RequestContext,
        params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        messages = []
        for msg in params.messages:
            role = msg.role
            text = ""
            if hasattr(msg.content, "text"):
                text = msg.content.text
            elif isinstance(msg.content, TextContent):
                text = msg.content.text
            messages.append({"role": role, "content": text})

        response = await claude.chat(messages)
        content = getattr(response, "content", "") or ""
        return CreateMessageResult(
            role="assistant",
            model=claude.model,
            content=TextContent(type="text", text=content),
        )

    return _sample


async def create_chat(
    stack: AsyncExitStack,
    logging_callback: Callable[[Any], Awaitable[Any]] | None = None,
) -> CliChat:
    settings, servers = load_settings()

    claude = Claude(
        provider=settings.provider,
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )

    async def _default_log(msg: Any) -> None:
        logger.debug("MCP log: %s", msg)
    cb = logging_callback or _default_log

    roots_manager = RootsManager(settings.roots)
    sampling_callback = _build_sampling_callback(claude)

    doc_client, clients = await create_servers(
        servers,
        stack=stack,
        transport=os.getenv("MCP_TRANSPORT", "sse"),
        roots=settings.roots,
        sampling_callback=sampling_callback,
        logging_callback=cb,
    )

    chat = CliChat(
        doc_client=doc_client,
        clients=clients,
        claude_service=claude,
        max_context_tokens=settings.max_context_tokens,
        roots_manager=roots_manager,
    )

    await chat.initialize()
    return chat
