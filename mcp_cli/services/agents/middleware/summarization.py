from __future__ import annotations

import asyncio
from typing import Any

from mcp_cli.services.agents.middleware.base import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware


@register_middleware
class SummarizationMiddleware(AgentMiddleware):
    """Manages both short-term and long-term memory for agent conversations.
    
    Short-term memory: current message history, automatically compressed via summarization
    when exceeding thresholds. Maintains recent context intact.
    
    Long-term memory: persistent facts/preferences stored in files, injected into
    system prompts for cross-thread memory continuity.
    """

    def __init__(
        self,
        max_messages: int = 100,
        summary_prompt: str = "",
        token_threshold: int = 0,
        keep_messages: int = 10,
        long_term_memory_paths: list[str] | None = None,
        max_long_term_memories: int = 5,
    ):
        self._max_messages = max_messages
        self._token_threshold = token_threshold
        self._summary_prompt = summary_prompt or (
            "Condense the following conversation into a concise summary "
            "that preserves all factual information, decisions, and "
            "user preferences. Omit greetings and pleasantries."
        )
        self._has_summarized = False
        self._keep_messages = keep_messages
        self._long_term_memory_paths = long_term_memory_paths or []
        self._max_long_term_memories = max_long_term_memories
        self._short_term_memory: list[dict[str, Any]] = []
        self._long_term_memory: list[dict[str, Any]] = []
        self._loaded_long_term: dict[str, str] = {}

    @property
    def token_threshold(self) -> int:
        return self._token_threshold

    @token_threshold.setter
    def token_threshold(self, value: int) -> None:
        self._token_threshold = value

    # ------------------------------------------------------------------
    # Long-term memory API
    # ------------------------------------------------------------------

    async def load_long_term_memory(self, memory_store: Any) -> dict[str, str]:
        """Load long-term memory files from persistent store."""
        loaded = {}
        for path in self._long_term_memory_paths:
            try:
                content = await asyncio.to_thread(memory_store.read, "default", path)
                if content:
                    loaded[path] = content
            except Exception as exc:
                # Log but don't fail - memory loading is non-critical
                pass
        self._loaded_long_term = loaded
        return loaded

    def build_long_term_memory_block(self) -> str:
        """Build the <agent_memory> block for system prompt injection."""
        if not self._loaded_long_term:
            return ""
        
        blocks = []
        for path, content in self._loaded_long_term.items():
            blocks.append(f"# Memory: {path}\n{content}")
        
        if not blocks:
            return ""
        
        combined = "\n\n---\n".join(blocks)
        return f"\n\n<agent_memory>\n{combined}\n</agent_memory>"

    def inject_long_term_memory(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Inject long-term memory into the system prompt."""
        memory_block = self.build_long_term_memory_block()
        if not memory_block:
            return messages
        
        # Find system message to inject into
        for msg in messages:
            if msg.get("role") == "system":
                existing = msg.get("content", "")
                if "<agent_memory>" not in existing:
                    msg["content"] = existing + memory_block
                return messages
        
        # No system message - add one with just memory
        return [{"role": "system", "content": memory_block}] + messages

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._has_summarized = False
        return self.inject_long_term_memory(messages)

    def should_summarize(
        self,
        messages: list[dict[str, Any]],
        total_tokens: int | None = None,
    ) -> bool:
        if self._has_summarized:
            return False
        non_system = [m for m in messages if m.get("role") != "system"]
        if len(non_system) > self._max_messages:
            return True
        return (
            self._token_threshold > 0
            and total_tokens is not None
            and total_tokens > self._token_threshold
        )

    def mark_summarized(self) -> None:
        self._has_summarized = True

    def build_summary_messages(
        self,
        messages: list[dict[str, Any]],
        summary_text: str,
    ) -> list[dict[str, Any]]:
        """Replace old messages with a summary, keeping the last N turns."""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        keep_count = self._keep_messages
        recent = non_system[-keep_count:] if keep_count > 0 else non_system

        summary_msg: dict[str, Any] = {
            "role": "assistant",
            "content": (
                f"[Earlier conversation summarized: {summary_text}]"
            ),
        }

        return system_msgs + [summary_msg] + recent
