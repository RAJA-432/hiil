from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_cli.services.logging import get_logger

if TYPE_CHECKING:
    from mcp_cli.services.notification_bus import NotificationBus

logger = get_logger("chat")


class RecoveryHandler:
    def __init__(
        self,
        streamer: Any,
        usage: Any,
        claude_model: str,
        session_id: str,
        bus: NotificationBus | None = None,
        max_correction_attempts: int = 2,
    ) -> None:
        self.streamer = streamer
        self.usage = usage
        self.claude_model = claude_model
        self.session_id = session_id
        self.bus = bus
        self.recovery_attempted = False
        self.correction_attempts = 0
        self.max_correction_attempts = max_correction_attempts

    def reset_turn(self) -> None:
        self.recovery_attempted = False
        self.correction_attempts = 0

    def should_retry_format(self) -> bool:
        return self.correction_attempts < self.max_correction_attempts

    def begin_format_retry(self) -> None:
        self.correction_attempts += 1

    def maybe_reset_recovery(self, prev_tool_used: bool, tool_calls: Any) -> None:
        if prev_tool_used and not tool_calls:
            self.recovery_attempted = False

    async def maybe_recover(
        self,
        prev_tool_used: bool,
        tool_calls: Any,
        content: str,
        messages: list[dict[str, Any]],
        on_chunk: Any = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Detect silent failures and return a recovery message dict on success."""
        bus = self.bus
        # --- RECOVERY LOGIC: Silent Failure Detection ---
        # If we just executed tools in the previous iteration AND now we get empty content
        # with no tool calls, this is a "silent failure" - the model didn't respond after
        # seeing tool results.
        if not (prev_tool_used and not tool_calls and not content.strip()):
            return None
        if not self.recovery_attempted:
            if bus:
                await bus.push_log("warn", "Silent failure detected: model returned empty response after tool execution. Initiating recovery...")
            # Recovery: strip all tools and force a summary
            recovery_messages = messages + [{
                "role": "system",
                "content": "You have received tool results above but provided no response. Summarize the tool results immediately and provide your final answer."
            }]
            self.recovery_attempted = True
            recovery_message, rec_in, rec_out = await self.streamer.chat(
                recovery_messages, tools=[], on_chunk=on_chunk, response_format=response_format,
            )
            await self.usage.async_record(self.claude_model, rec_in, rec_out, self.session_id)

            if hasattr(recovery_message, "model_dump"):
                rec_dict = recovery_message.model_dump(exclude_unset=True)
            else:
                rec_dict = {
                    "role": "assistant",
                    "content": getattr(recovery_message, "content", "") or "",
                }
                if hasattr(recovery_message, "tool_calls") and recovery_message.tool_calls:
                    rec_dict["tool_calls"] = recovery_message.tool_calls

            if rec_dict.get("content"):
                if bus:
                    await bus.push_log("info", "Recovery successful.")
                return rec_dict

            if bus:
                await bus.push_log("warn", "Recovery attempt also returned empty content. Continuing with normal flow...")
        return None

    async def retry_correction(
        self,
        answer: str,
        user_input: str,
        issues: list[str],
        messages: list[dict[str, Any]],
        openai_tools: list[dict[str, Any]],
    ) -> str:
        if self.correction_attempts >= self.max_correction_attempts:
            return ""
        self.correction_attempts += 1
        issue_text = "\n".join(f"- {issue}" for issue in issues)
        correction = (
            "Your previous response was flagged by a verification pass. "
            f"Address the following issues:\n{issue_text}"
        )
        retry_messages = [*messages, {"role": "user", "content": correction}]
        try:
            message, input_tokens, output_tokens = await self.streamer.chat(
                retry_messages,
                tools=openai_tools if openai_tools else None,
            )
            await self.usage.async_record(self.claude_model, input_tokens, output_tokens, self.session_id)
            return message.content or ""
        except Exception as exc:
            logger.warning("verifier correction retry failed, returning original answer: %s", exc)
            return ""
