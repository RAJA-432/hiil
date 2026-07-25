from __future__ import annotations

from typing import Any

from mcp_cli.services.agents.middleware import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware


@register_middleware
class SummarizationMiddleware(AgentMiddleware):
    """Auto-compresses conversation history when the message count exceeds
    a threshold.

    Simulates deepagents' built-in ``SummarizationMiddleware``: when the
    message list grows past ``max_messages`` the oldest messages are
    condensed into a single summary message, keeping recent turns intact.

    Unlike the deepagents version which fires at 85 % of the model's real
    context window, this one uses a simple message-count threshold for
    predictable behaviour and easy testing.
    """

    def __init__(self, max_messages: int = 30, summary_prompt: str = ""):
        self._max_messages = max_messages
        self._summary_prompt = summary_prompt or (
            "Condense the following conversation into a concise summary "
            "that preserves all factual information, decisions, and "
            "user preferences. Omit greetings and pleasantries."
        )
        self._has_summarized = False

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._has_summarized = False
        return messages

    def should_summarize(self, messages: list[dict[str, Any]]) -> bool:
        non_system = [m for m in messages if m.get("role") != "system"]
        return len(non_system) > self._max_messages and not self._has_summarized

    def build_summary_messages(
        self,
        messages: list[dict[str, Any]],
        summary_text: str,
    ) -> list[dict[str, Any]]:
        """Replace old messages with a summary, keeping the last N turns."""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        keep_count = self._max_messages // 2
        recent = non_system[-keep_count:] if keep_count > 0 else non_system

        summary_msg: dict[str, Any] = {
            "role": "assistant",
            "content": (
                f"[Earlier conversation summarized: {summary_text}]"
            ),
        }

        return system_msgs + [summary_msg] + recent
