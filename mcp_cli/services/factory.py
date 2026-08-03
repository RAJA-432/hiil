from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import AsyncExitStack
from typing import Any, cast

from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    TextContent,
)

from mcp_cli.config import Settings, load_settings
from mcp_cli.services.chat import CliChat
from mcp_cli.services.claude import LLMClient
from mcp_cli.services.logging import get_logger
from mcp_cli.services.roots import RootsManager
from mcp_cli.services.server_manager import create_servers
from mcp_cli.services.vector_store import VectorStore, create_vector_store

logger = get_logger("factory")


def _build_sampling_callback(
    claude: LLMClient,
) -> Callable[[RequestContext, CreateMessageRequestParams], Coroutine[Any, Any, CreateMessageResult]]:
    """Return a sampling callback that delegates LLM inference to the *claude* service."""

    async def _sample(
        context: RequestContext,
        params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        messages = []
        for msg in params.messages:
            role = msg.role
            if hasattr(msg.content, "text"):
                messages.append({"role": role, "content": msg.content.text})
            elif isinstance(msg.content, list):
                parts = []
                for part in msg.content:
                    if hasattr(part, "text"):
                        parts.append({"type": "text", "text": part.text})
                    elif hasattr(part, "data") and hasattr(part, "mimeType"):
                        parts.append({"type": "image_url", "image_url": {"url": f"data:{part.mimeType};base64,{part.data}"}})
                    else:
                        parts.append({"type": "text", "text": str(part)})
                messages.append({"role": role, "content": parts})
            elif isinstance(msg.content, TextContent):
                messages.append({"role": role, "content": msg.content.text})
            else:
                messages.append({"role": role, "content": str(msg.content)})

        response = await claude.chat(messages)
        content = getattr(response, "content", "") or ""
        return CreateMessageResult(
            role="assistant",
            model=claude.model,
            content=TextContent(type="text", text=content),
        )

    return _sample


class ChatBuilder:
    """Builds isolated CliChat instances that reuse one set of MCP servers."""

    def __init__(
        self,
        settings: Settings,
        claude: LLMClient,
        roots_manager: RootsManager,
        doc_client: Any,
        clients: dict[str, Any],
    ) -> None:
        self._settings = settings
        self._claude = claude
        self._roots_manager = roots_manager
        self._doc_client = doc_client
        self._clients = clients

    async def create(self, session_id: str = "default") -> CliChat:
        chat = CliChat(
            doc_client=self._doc_client,
            clients=self._clients,
            claude_service=self._claude,
            max_context_tokens=self._settings.max_context_tokens,
            roots_manager=self._roots_manager,
            enable_verification=self._settings.enable_verification,
            verifier_model=self._settings.verifier_model or None,
            enable_moderation=self._settings.enable_moderation,
            moderation_deny_list=list(self._settings.moderation_deny_list or []),
            discovery_guard=self._settings.discovery_guard,
            intent_routing=self._settings.intent_routing,
            session_id=session_id,
        )

        if self._settings.vector_backend != "sqlite":
            original = chat.vector_store
            store = create_vector_store(self._settings.vector_backend)
            chat.vector_store = store
            chat.rag.vector_store = cast(VectorStore, store)
            original.close()

        await chat.initialize()
        return chat


async def create_chat_factory(
    stack: AsyncExitStack,
    logging_callback: Callable[[Any], Awaitable[Any]] | None = None,
) -> ChatBuilder:
    settings, servers = await asyncio.to_thread(load_settings)

    claude = LLMClient(
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

    return ChatBuilder(
        settings=settings,
        claude=claude,
        roots_manager=roots_manager,
        doc_client=doc_client,
        clients=clients,
    )


async def create_chat(
    stack: AsyncExitStack,
    logging_callback: Callable[[Any], Awaitable[Any]] | None = None,
) -> CliChat:
    builder = await create_chat_factory(stack, logging_callback=logging_callback)
    return await builder.create()
