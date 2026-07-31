from __future__ import annotations

from typing import Any

from mcp_cli.services.agents.middleware import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware


@register_middleware
class SummarizationMiddleware(AgentMiddleware):
    """Auto-compresses conversation history when the message count or token
    usage exceeds a threshold.

    Simulates deepagents' built-in ``SummarizationMiddleware``: when the
    message list grows past ``max_messages`` (or, when ``token_threshold``
    is set, past that many cumulative tokens) the oldest messages are
    condensed into a single summary message, keeping recent turns intact.

    Unlike the deepagents version which fires at 85 % of the model's real
    context window, the count trigger uses a simple message-count threshold
    for predictable behaviour and easy testing. Token-based triggering is
    available via ``token_threshold`` (``0`` = disabled), e.g. 85 % of the
    configured ``AgentConfig.token_budget``.
    """

    def __init__(
        self,
        max_messages: int = 30,
        summary_prompt: str = "",
        token_threshold: int = 0,
    ):
        self._max_messages = max_messages
        self._token_threshold = token_threshold
        self._summary_prompt = summary_prompt or (
            "Condense the following conversation into a concise summary "
            "that preserves all factual information, decisions, and "
            "user preferences. Omit greetings and pleasantries."
        )
        self._has_summarized = False

    @property
    def token_threshold(self) -> int:
        return self._token_threshold

    @token_threshold.setter
    def token_threshold(self, value: int) -> None:
        self._token_threshold = value

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._has_summarized = False
        return messages

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

        keep_count = self._max_messages // 2
        recent = non_system[-keep_count:] if keep_count > 0 else non_system

        summary_msg: dict[str, Any] = {
            "role": "assistant",
            "content": (
                f"[Earlier conversation summarized: {summary_text}]"
            ),
        }

        return system_msgs + [summary_msg] + recent
