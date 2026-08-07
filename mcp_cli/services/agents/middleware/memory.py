from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_cli.services.agents.middleware.base import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware

if TYPE_CHECKING:
    from mcp_cli.services.agents.memory import AgentMemoryStore, MemoryScope


_MEMORY_GUIDELINES = (
    "You have access to persistent memory files. Load relevant context from "
    "them before acting, and when the user shares facts, preferences, or "
    "decisions that should carry forward to future conversations, update the "
    "memory file by writing it with the file tool. Only store information "
    "that is safe and useful in future conversations. Do not store secrets "
    "such as API keys, credentials, tokens, or passwords."
)


@register_middleware
class MemoryMiddleware(AgentMiddleware):
    """Persistent long-term memory across threads (Deep Agents model).

    Memory is plain files on the agent's filesystem. On each run the
    middleware loads the configured memory files from the persistent store
    and appends their contents to the system prompt inside an
    ``<agent_memory>`` block. The agent updates memory by editing those
    files; the new content is available on the next run.
    """

    def __init__(
        self,
        memory_files: list[str] | None = None,
        memory_store: AgentMemoryStore | None = None,
        memory_scope: MemoryScope | None = None,
        instructions: str = "",
    ):
        self._memory_files = memory_files or []
        self._memory_store = memory_store
        self._memory_scope = memory_scope
        self._instructions = instructions or _MEMORY_GUIDELINES
        self._loaded: dict[str, str] = {}

    @property
    def memory_scope(self) -> MemoryScope | None:
        return self._memory_scope

    # ------------------------------------------------------------------
    # Memory loading / persistence
    # ------------------------------------------------------------------

    async def load_memory(self, agent_id: str, store: AgentMemoryStore | None = None) -> dict[str, str]:
        """Load the configured memory files from the persistent store."""
        store = store or self._memory_store
        if store is None or not self._memory_files:
            self._loaded = {}
            return self._loaded
        namespace = self._memory_scope.namespace if self._memory_scope else None
        loaded: dict[str, str] = {}
        for path in self._memory_files:
            content = await asyncio_to_thread(store.read, agent_id, path, namespace)
            if content is not None:
                loaded[path] = content
        self._loaded = loaded
        return loaded

    async def persist_memory(self, agent_id: str, path: str, content: str, store: AgentMemoryStore | None = None) -> None:
        """Write an updated memory file back to the persistent store."""
        store = store or self._memory_store
        if store is None:
            return
        namespace = self._memory_scope.namespace if self._memory_scope else None
        await asyncio_to_thread(store.write, agent_id, path, content, namespace)
        self._loaded[path] = content

    # ------------------------------------------------------------------
    # System prompt injection
    # ------------------------------------------------------------------

    def build_memory_block(self) -> str:
        """Build the ``<agent_memory>`` block from loaded memory files."""
        if not self._loaded:
            return ""
        sections = [
            f"# Memory: {path}\n{content}"
            for path, content in self._loaded.items()
            if content
        ]
        if not sections:
            return ""
        combined = "\n\n---\n".join(sections)
        return f"\n\n<agent_memory>\n{combined}\n</agent_memory>"

    def inject_memory(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Inject the loaded memory block into the system prompt."""
        memory_block = self.build_memory_block()
        if not memory_block:
            return messages
        for msg in messages:
            if msg.get("role") == "system":
                existing = msg.get("content", "")
                if "<agent_memory>" not in existing:
                    msg["content"] = existing + memory_block
                return messages
        return [{"role": "system", "content": memory_block}] + messages

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.inject_memory(messages)


def asyncio_to_thread(fn: Any, *args: Any, **kwargs: Any):
    import asyncio
    return asyncio.to_thread(fn, *args, **kwargs)
