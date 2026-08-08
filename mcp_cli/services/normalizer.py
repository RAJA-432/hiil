"""
Response and tool-call normalization for the LLM transport client.

Normalizes non-standard responses from OpenAI-compatible proxies into
standard ``ChatCompletionMessage`` objects.
"""

from __future__ import annotations

from typing import Any

from openai.types.chat import ChatCompletionMessage

from mcp_cli.services.logging import get_logger

logger = get_logger("claude")


def _normalize_tool_call(tc: Any) -> Any:
    """Ensure tool_call has proper OpenAI function-call structure."""
    if isinstance(tc, dict):
        if "function" not in tc and ("name" in tc or "arguments" in tc):
            # Wrap legacy format into function structure
            tc["function"] = {
                "name": tc.get("name", "unknown"),
                "arguments": tc.get("arguments", "{}"),
            }
    return tc


class ResponseNormalizer:
    def normalize_tool_call(self, tc: Any) -> Any:
        """Ensure tool_call has proper OpenAI function-call structure."""
        return _normalize_tool_call(tc)

    def merge_tool_call(self, tool_calls: dict[int, dict[str, Any]], tc: Any) -> None:
        """Accumulate a streamed tool-call delta into the per-index structure."""
        idx = tc.index
        if idx not in tool_calls:
            tool_calls[idx] = {
                "id": tc.id or "",
                "function": {
                    "name": tc.function.name or "",
                    "arguments": tc.function.arguments or "",
                },
            }
        else:
            if tc.function and tc.function.arguments:
                tool_calls[idx]["function"]["arguments"] += tc.function.arguments
            if tc.function and tc.function.name:
                tool_calls[idx]["function"]["name"] += tc.function.name
            if tc.id:
                tool_calls[idx]["id"] += tc.id

    def normalize_message(self, response: Any) -> ChatCompletionMessage:
        """Normalize a chat-completion response into a ChatCompletionMessage."""
        # --- Normalize non-standard responses -------------------------------
        # Some OpenCode-style proxies reply with the assistant text directly.
        if isinstance(response, str):
            return ChatCompletionMessage(role="assistant", content=response)

        # A raw dict (unparsed) response: pull the message out if present.
        if isinstance(response, dict):
            if not response.get("choices"):
                return ChatCompletionMessage(role="assistant", content="")
            msg = response["choices"][0].get("message", {})
            # Normalize tool_calls if present
            tool_calls = msg.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                # Ensure each tool_call has proper structure
                tool_calls = [
                    tc if hasattr(tc, "function") else self.normalize_tool_call(tc)
                    for tc in tool_calls
                ]
            return ChatCompletionMessage(
                role="assistant",
                content=msg.get("content"),
                tool_calls=tool_calls,
            )

        # Standard OpenAI response - validate before accessing
        try:
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message
        except (AttributeError, IndexError) as e:
            logger.warning("Unexpected response structure: %s", e)
            return ChatCompletionMessage(role="assistant", content="")

        # Fallback for empty response
        return ChatCompletionMessage(role="assistant", content="")
