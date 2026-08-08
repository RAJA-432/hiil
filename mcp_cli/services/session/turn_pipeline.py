from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from mcp_cli.services.builtin_tools import _DELEGATE_TOOLS
from mcp_cli.services.logging import get_logger
from mcp_cli.services.session.image_input import ImageInputHandler
from mcp_cli.services.session.recovery import RecoveryHandler
from mcp_cli.services.token_monitor import format_status
from mcp_cli.services.usage import count_tokens

if TYPE_CHECKING:
    from mcp_cli.services.notification_bus import NotificationBus

logger = get_logger("chat")


class TurnPipeline:
    def __init__(
        self,
        claude: Any,
        streamer: Any,
        context: Any,
        rag: Any,
        doc_injector: Any,
        tool_runner: Any,
        registry: Any,
        usage: Any,
        history: Any,
        moderation: Any,
        verifier: Any,
        bus: NotificationBus | None,
        max_tool_iterations: int,
        messages: list[dict[str, Any]],
        session_id: str,
        tools_by_name: dict[str, dict[str, Any]],
        openai_tools: list[dict[str, Any]],
        default_response_format: dict[str, Any] | None,
        recovery: RecoveryHandler,
        push_state: Any,
        validate_output: Any,
        auto_index_wrapper: Any,
        can_process_images: Any,
        token_monitor: Any = None,
        prompt_budget: Any = None,
    ) -> None:
        self.claude = claude
        self.streamer = streamer
        self.context = context
        self.rag = rag
        self.doc_injector = doc_injector
        self.tool_runner = tool_runner
        self.registry = registry
        self.usage = usage
        self.history = history
        self.moderation = moderation
        self.verifier = verifier
        self.bus = bus
        self.max_tool_iterations = max_tool_iterations
        self.messages = messages
        self.session_id = session_id
        self.tools_by_name = tools_by_name
        self.openai_tools = openai_tools
        self.default_response_format = default_response_format
        self._recovery = recovery
        self._push_state = push_state
        self._validate_output = validate_output
        self._auto_index_wrapper = auto_index_wrapper
        self._can_process_images = can_process_images
        self.token_monitor = token_monitor
        self.prompt_budget = prompt_budget
        self._image_handler = ImageInputHandler()
        self.auto_index_task: asyncio.Task | None = None

    async def run(
        self,
        user_input: str,
        images: list[str] | None = None,
        on_chunk: Any = None,
        response_format: dict[str, Any] | None = None,
        bus: NotificationBus | None = None,
        on_tool_event: Any = None,
        on_approval: Any = None,
    ) -> str:
        if bus is not None:
            self.bus = bus
            self._recovery.bus = bus
        bus = self.bus

        augmented = await self.doc_injector.resolve(user_input)

        rag_context = ""
        try:
            retrieve = getattr(self.rag, "retrieve_compressed", None)
            if self.prompt_budget is not None and callable(retrieve):
                max_tokens = max(1, int(self.prompt_budget.context_budget()))
                rag_results = await retrieve(
                    user_input, top_k=3, min_score=0.25, max_tokens=max_tokens,
                )
            else:
                rag_results = await self.rag.retrieve(user_input, top_k=3, min_score=0.25)
            if rag_results:
                rag_context = self.rag.format_context(rag_results)
                augmented = (
                    f"Relevant knowledge base context:\n{rag_context}\n\n"
                    f"User question: {augmented}"
                )
                if bus:
                    bus.push_rag(rag_results)
        except Exception:
            logger.warning("RAG retrieval failed, continuing without knowledge base context")

        self.auto_index_task = asyncio.create_task(
            self._auto_index_wrapper(user_input), name="auto_index"
        )

        augmented, images = await self._image_handler.augment_text(
            augmented, images, self._can_process_images, bus,
        )

        user_content, save_content = self._image_handler.build_user_message(augmented, images)
        self.messages.append({"role": "user", "content": user_content})
        await self.history.async_save_message(self.session_id, "user", save_content)

        iterations = 0
        tool_used = False
        prev_tool_used = False  # Track if previous iteration used tools
        tool_events: list[str] = []
        await self._push_state("THINKING", iteration=1)
        while True:
            iterations += 1

            # Track if previous iteration used tools for silent failure detection
            prev_tool_used = tool_used
            tool_used = False  # Reset for this iteration
            active_tool_names = self.registry.resolve_tools(user_input)
            active_tools = [self.tools_by_name[name]["openai"]
                            for name in active_tool_names if name in self.tools_by_name]
            tools_tokens = count_tokens(json.dumps(active_tools), self.claude.model) if active_tools else 0
            self.messages = self.context.trim(self.messages, tools_tokens)

            # Log routing metrics
            if bus:
                await bus.push_log("debug", f"Tool routing: selected {len(active_tool_names)} tools ({tools_tokens} tokens)")
                if hasattr(bus, 'push_metric'):
                    await bus.push_metric("tool_schema_tokens", tools_tokens)
                    await bus.push_metric("tool_count", len(active_tool_names))

            if iterations > self.max_tool_iterations:
                await self._push_state("DONE")
                if bus:
                    await bus.push_log("warn", f"Stopped after {self.max_tool_iterations} tool iterations.")
                return await self._moderate_output(
                    f"[stopped] Maximum tool calls ({self.max_tool_iterations}) reached.", bus,
                )

            if bus:
                await bus.push_log("info", f"Calling LLM (iteration {iterations})...")

            fmt = response_format or self.default_response_format
            message, input_tokens, output_tokens = await self.streamer.chat(
                self.messages, tools=active_tools, on_chunk=on_chunk, response_format=fmt,
            )
            await self.usage.async_record(self.claude.model, input_tokens, output_tokens, self.session_id)

            if self.token_monitor is not None:
                try:
                    status = self.token_monitor.record(input_tokens, output_tokens)
                    if bus and status["level"] != "ok":
                        await bus.push_log(status["level"], format_status(status))
                except Exception:
                    logger.debug("token monitor record failed", exc_info=True)

            if bus:
                await bus.push_log("debug", f"Tokens: {input_tokens} in / {output_tokens} out")

            if hasattr(message, "model_dump"):
                msg_dict = message.model_dump(exclude_unset=True)
            else:
                msg_dict = {
                    "role": "assistant",
                    "content": getattr(message, "content", "") or "",
                }
                if hasattr(message, "tool_calls") and message.tool_calls:
                    msg_dict["tool_calls"] = message.tool_calls
            if msg_dict.get("content") is None:
                msg_dict["content"] = ""
            self.messages.append(msg_dict)
            await self.history.async_save_message(self.session_id, "assistant", msg_dict["content"])

            tool_calls = getattr(message, "tool_calls", None)

            content = message.content or ""
            rec_dict = await self._recovery.maybe_recover(
                prev_tool_used, tool_calls, content, self.messages,
                on_chunk=on_chunk, response_format=fmt,
            )
            if rec_dict is not None:
                self.messages.append(rec_dict)
                await self.history.async_save_message(self.session_id, "assistant", rec_dict["content"])
                await self._push_state("REPORTING")
                final_answer = await self._finalize_output(
                    rec_dict["content"],
                    user_input,
                    rag_context,
                    tool_used,
                    "\n".join(tool_events),
                    bus,
                )
                if bus:
                    await bus.push_log("info", "Response complete (recovery).")
                    await bus.push_done()
                await self._push_state("DONE")
                return final_answer

            # Reset recovery flag for next iteration
            self._recovery.maybe_reset_recovery(prev_tool_used, tool_calls)

            if not tool_calls:
                await self._push_state("REPORTING")
                is_valid, err = self._validate_output(message.content or "")
                if is_valid:
                    final_answer = await self._finalize_output(
                        message.content or "",
                        user_input,
                        rag_context,
                        tool_used,
                        "\n".join(tool_events),
                        bus,
                    )
                    if bus:
                        await bus.push_log("info", "Response complete.")
                        await bus.push_done()
                    await self._push_state("DONE")
                    return final_answer

                logger.warning("output validation failed: %s", err)
                from mcp_cli.services.chat import _inc_validation_error
                _inc_validation_error()
                logger.info(
                    "refinement_audit skill=%s valid=%s error=%s",
                    (self.default_response_format or {}).get("json_schema", {}).get("name", "unknown"),
                    is_valid,
                    err,
                )

                if self._recovery.should_retry_format():
                    self._recovery.begin_format_retry()
                    self.messages.append({
                        "role": "user",
                        "content": f"Your previous response did not match the required format. Error: {err}\n\nPlease reformat your response to strictly follow the output schema requirements. Return ONLY valid content matching the expected format.",
                    })
                    continue

                final_answer = await self._finalize_output(
                    message.content or "",
                    user_input,
                    rag_context,
                    tool_used,
                    "\n".join(tool_events),
                    bus,
                )
                if bus:
                    await bus.push_log("warn", "Max correction attempts reached, returning raw output.")
                    await bus.push_done()
                await self._push_state("DONE")
                return final_answer

            if bus:
                await bus.push_log("info", f"Executing {len(tool_calls)} tool(s)...")

            tool_used = True
            tool_names: list[str] = []
            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                name = getattr(fn, "name", None) or getattr(tc, "name", "") or "tool"
                args = getattr(fn, "arguments", None) or ""
                tool_names.append(name)
                tool_events.append(f"{name}({args})" if args else name)

            await self._push_state(
                "DELEGATING" if any(n in _DELEGATE_TOOLS for n in tool_names) else "EXECUTING",
                iteration=iterations,
            )
            tool_results = await self.tool_runner.execute_tool_calls(
                tool_calls,
                on_tool_event=on_tool_event,
                on_approval=on_approval,
            )
            self.messages.extend(tool_results)
            self.messages = self.context.trim(self.messages, tools_tokens)

    async def _moderate_output(self, text: str, bus: NotificationBus | None) -> str:
        moderation = self.moderation
        if moderation is None:
            return text
        try:
            ok, reason = moderation.check_output(text)
        except Exception:
            return text
        if ok:
            return text
        if bus:
            await bus.push_log("warn", f"Output blocked by moderation ({reason}).")
        return f"[blocked] Your message was flagged by moderation ({reason})."

    async def _record_verifier_usage(self, answer: str, user_input: str, rag_context: str, tool_summary: str) -> None:
        try:
            prompt = f"User question:\n{user_input}"
            if rag_context:
                prompt += f"\n\nReference context:\n{rag_context}"
            if tool_summary:
                prompt += f"\n\nTool results:\n{tool_summary}"
            prompt += f"\n\nAssistant answer:\n{answer}"
            input_tokens = count_tokens(prompt, self.claude.model)
            output_tokens = count_tokens(answer, self.claude.model)
            await self.usage.async_record(self.claude.model, input_tokens, output_tokens, self.session_id)
        except Exception as exc:
            logger.debug("verifier usage recording failed: %s", exc)

    async def _verify_answer(
        self,
        answer: str,
        user_input: str,
        rag_context: str,
        tool_used: bool,
        tool_summary: str,
        bus: NotificationBus | None,
    ) -> str:
        verifier = self.verifier
        if verifier is None or not (tool_used or rag_context):
            return answer
        try:
            verdict = await verifier.verify(
                answer,
                user_input,
                rag_context=rag_context,
                tool_summary=tool_summary,
            )
            await self._record_verifier_usage(answer, user_input, rag_context, tool_summary)
            if verdict.valid:
                if bus:
                    await bus.push_log("info", "Verified by critique pass.")
                return answer
            if verdict.revised:
                if bus:
                    await bus.push_log("info", "Verified by critique pass.")
                    await bus.push_log("warn", "Answer revised by verifier.")
                    await bus.push_log("info", f"Original answer: {answer}")
                return verdict.revised
            if verdict.issues:
                retried = await self._recovery.retry_correction(
                    answer, user_input, verdict.issues, self.messages, self.openai_tools,
                )
                if retried:
                    if bus:
                        await bus.push_log("info", "Verified by critique pass.")
                    return retried
            if bus:
                await bus.push_log("info", "Verified by critique pass.")
            return answer
        except Exception as exc:
            logger.warning("verification failed, returning original answer: %s", exc)
            return answer

    async def _finalize_output(
        self,
        answer: str,
        user_input: str,
        rag_context: str,
        tool_used: bool,
        tool_summary: str,
        bus: NotificationBus | None,
    ) -> str:
        final = await self._verify_answer(answer, user_input, rag_context, tool_used, tool_summary, bus)
        return await self._moderate_output(final, bus)
