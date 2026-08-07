from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from mcp_cli.services.agents.backend import VirtualBackend
from mcp_cli.services.agents.interrupts import (
    ActionRequest,
    AgentInterruptError,
    ResumeDecision,
)
from mcp_cli.services.agents.memory import AgentMemoryStore
from mcp_cli.services.agents.middleware.base import MiddlewarePipeline
from mcp_cli.services.agents.middleware.memory import MemoryMiddleware
from mcp_cli.services.agents.models import (
    AgentConfig,
    AgentResult,
    AgentState,
    PhaseTransition,
    _normalize_interrupt,
)
from mcp_cli.services.agents.permissions import PermissionEnforcer
from mcp_cli.services.logging import get_logger
from mcp_cli.services.tool_router import ToolRouter

if TYPE_CHECKING:
    from mcp_cli.services.chat import CliChat
    from mcp_cli.services.notification_bus import NotificationBus

logger = get_logger("agent_runner")

_MEMORY_STORE: AgentMemoryStore | None = None


def _get_memory_store() -> AgentMemoryStore:
    global _MEMORY_STORE
    if _MEMORY_STORE is None:
        from pathlib import Path
        _MEMORY_STORE = AgentMemoryStore(Path.cwd() / ".agent_memory")
    return _MEMORY_STORE


class AgentRunner:
    """Runs an isolated agent within a parent ``CliChat`` session.

    Adds three deepagents-inspired features on top of the basic loop:
    * **Human-in-the-loop** — gated tools pause execution for approval/edit/reject
    * **Per-agent memory** — persistent files injected into context before run
    * **Filesystem permissions** — allow/deny per operation per path
    """

    def __init__(
        self,
        config: AgentConfig,
        parent_chat: CliChat,
        bus: NotificationBus | None = None,
    ):
        self.agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        self.config = config
        self.parent_chat = parent_chat

        self.bus = bus
        self._state = AgentState(
            agent_id=self.agent_id,
            config=config,
            status="idle",
            created_at=datetime.now(UTC),
            last_active=datetime.now(UTC),
        )

        self._messages: list[dict[str, Any]] = []
        self._tool_calls_made = 0
        self._summarized_archive: list[dict[str, Any]] = []

        # Build the tool router from parent's tool registry
        self.tool_router = ToolRouter(
            tools_by_name=parent_chat.tools_by_name,
            clients=parent_chat.clients,
            capabilities=config.capabilities,
            discovery=getattr(parent_chat, "discovery_tracker", None),
        )

        # Permission enforcer for file operations
        self._perm_enforcer = PermissionEnforcer(config.permissions) if config.permissions else None

        # Virtual backend (in-memory filesystem; never touches real disk by default)
        self._virtual_backend = VirtualBackend()

        # Memory store
        self._memory = _get_memory_store()

        # Middleware pipeline
        self._middleware = MiddlewarePipeline(config.middleware) if config.middleware else None

        # Ensure long-term memory middleware is active when memory files are configured
        self._memory_middleware = self._find_memory_middleware()
        if self._memory_middleware is None and config.memory_files:
            self._memory_middleware = MemoryMiddleware(
                memory_files=config.memory_files,
                memory_store=self._memory,
            )
            if self._middleware is None:
                self._middleware = MiddlewarePipeline([self._memory_middleware])
            else:
                self._middleware._middleware.insert(0, self._memory_middleware)

        # HITL resume synchronisation
        self._resume_event = asyncio.Event()
        self._resume_decisions: list[ResumeDecision] | None = None
        self._active_run: asyncio.Future[AgentResult] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._messages

    @property
    def summarized_archive(self) -> list[dict[str, Any]]:
        """Raw messages replaced by summarization, retained for auditing."""
        return list(self._summarized_archive)

    @property
    def virtual_files(self) -> dict[str, str]:
        return self._virtual_backend.files

    def add_route(self, virtual_prefix: str, real_path: str | Path) -> None:
        self._virtual_backend.add_route(virtual_prefix, str(real_path))

    async def run(self, task_input: str) -> AgentResult:
        self._state.status = "running"
        self._state.last_active = datetime.now(UTC)
        self._state.current_task_id = uuid.uuid4().hex[:8]
        self._tool_calls_made = 0
        self._state.pending_interrupt = None
        self._resume_decisions = None

        start = time.monotonic()
        output, error = "", None
        final_status: Literal["completed", "failed", "waiting"] = "completed"

        loop = asyncio.get_running_loop()
        self._active_run = loop.create_future()
        try:
            output = await asyncio.wait_for(
                self._execute_loop(task_input),
                timeout=self.config.timeout_seconds,
            )
        except AgentInterruptError as exc:
            self._state.pending_interrupt = None
            error, final_status = str(exc), "failed"
            logger.info("Agent %s stopped before completion: %s", self.agent_id, error)
        except TimeoutError:
            error = f"Agent timed out after {self.config.timeout_seconds}s"
            final_status = "failed"
            logger.warning("Agent %s: %s", self.agent_id, error)
        except Exception as exc:
            error, final_status = str(exc), "failed"
            logger.exception("Agent %s failed: %s", self.agent_id, error)

        result = await self._finish_run(start, output, error, final_status)
        active = self._active_run
        self._active_run = None
        if active is not None and not active.done():
            active.set_result(result)
        return result

    async def resume(self, decisions: list[ResumeDecision]) -> AgentResult:
        """Resume execution after a human-in-the-loop pause.

        Sets the resume event so the HITL gating loop in the active run wakes
        up, processes the decisions, and continues; then returns that run's
        final result.
        """
        pending = self._state.pending_interrupt
        if not pending:
            raise RuntimeError("No pending interrupt to resume from")

        self._resume_decisions = decisions
        self._state.pending_interrupt = None
        self._resume_event.set()

        if self._active_run is not None:
            return await self._active_run

        start = time.monotonic()
        output, error = "", None
        final_status: Literal["completed", "failed", "waiting"] = "completed"

        try:
            process_result = await self._process_decisions(decisions, pending)
            self._messages.append({
                "role": "tool",
                "tool_call_id": f"resume_{uuid.uuid4().hex[:8]}",
                "content": process_result,
            })

            output = await asyncio.wait_for(
                self._execute_loop(),
                timeout=self.config.timeout_seconds,
            )
        except AgentInterruptError as exc:
            self._state.pending_interrupt = exc.action_requests
            self._state.status = "waiting"
            final_status = "waiting"
            error, output = str(exc), ""
        except TimeoutError:
            error = f"Agent timed out after {self.config.timeout_seconds}s"
            final_status = "failed"
        except Exception as exc:
            error, final_status = str(exc), "failed"

        return await self._finish_run(start, output, error, final_status)

    async def _finish_run(
        self, start: float, output: str, error: str | None,
        final_status: Literal["completed", "failed", "waiting"],
    ) -> AgentResult:
        elapsed = time.monotonic() - start
        self._state.last_active = datetime.now(UTC)
        self._state.current_task_id = None
        self._state.result = {"output": output}
        self._state.status = final_status
        result = AgentResult(
            agent_id=self.agent_id,
            status=final_status,
            output=output,
            total_tokens=self._state.total_tokens,
            duration_seconds=round(elapsed, 2),
            tool_calls_made=self._tool_calls_made,
            error=error,
            pending_interrupt=self._state.pending_interrupt,
        )
        if final_status != "waiting":
            await self._set_phase("DONE")
        if self.bus and final_status != "waiting":
            await self.bus.push_done()
        return result

    async def stop(self) -> None:
        self._state.status = "failed"
        self._resume_event.set()
        if self.bus:
            await self.bus.push_log("warn", "Agent stopped by user")

    # ------------------------------------------------------------------
    # Execution loop
    # ------------------------------------------------------------------

    async def _execute_loop(self, task_input: str | None = None) -> str:
        if task_input is not None:
            await self._bootstrap(task_input)

        tools = self._agent_tools()

        for iteration in range(1, self.config.max_iterations + 1):
            if self.bus:
                await self.bus.push_log("info", f"LLM call (iteration {iteration})...")

            message = await self._chat_once(tools)
            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                return await self._settle_response(message.content)

            await self._maybe_summarize()

            await self._apply_tool_results(tool_calls, iteration)

        await self._persist_memory()
        return f"[stopped] Max iterations ({self.config.max_iterations}) reached."

    async def _bootstrap(self, task_input: str) -> None:
        """Prepare the message history for a fresh task run."""
        await self._set_phase("THINKING", iteration=1)
        await self._inject_memory()

        # Load persistent long-term memory into the memory middleware
        if self._memory_middleware is not None:
            await self._memory_middleware.load_memory(self.agent_id, self._memory)

        # Middleware: before_run
        if self._middleware:
            self._messages = self._middleware.before_run(self._messages)

        system_prompt = self.config.system_prompt or f"You are a {self.config.role} assistant."
        if not self._messages or self._messages[0].get("role") != "system":
            self._messages.insert(0, {"role": "system", "content": system_prompt})
        self._messages.append({"role": "user", "content": task_input})

    def _agent_tools(self) -> list[dict[str, Any]] | None:
        """Merge MCP tools with middleware extra tools."""
        tools = list(self.tool_router.openai_tools or [])
        if self._middleware:
            tools.extend(self._middleware.get_extra_tools())
        return tools or None

    async def _chat_once(self, tools: list[dict[str, Any]] | None) -> Any:
        """Run one LLM exchange, accounting tokens and appending the message."""
        message, input_tokens, output_tokens = await self.parent_chat.streamer.chat(
            self._messages, tools=tools,
        )
        self._state.total_tokens += input_tokens + output_tokens

        if self.config.token_budget and self._state.total_tokens > self.config.token_budget:
            raise RuntimeError(
                f"Agent '{self.config.name}' exceeded token budget "
                f"({self._state.total_tokens} > {self.config.token_budget})"
            )

        msg_dict = self._normalize_message(message)
        if msg_dict.get("content") is None:
            msg_dict["content"] = ""
        self._messages.append(msg_dict)
        return message

    async def _settle_response(self, content: str | None) -> str:
        """Finalize a non-tool response: REPORTING phase + memory persist."""
        await self._set_phase("REPORTING")
        await self._persist_memory()
        if self.bus:
            await self.bus.push_log("info", "Agent response complete.")
        return content or ""

    async def _maybe_summarize(self) -> bool:
        """Summarize when the summarization middleware requests it."""
        # Check summarization middleware
        from mcp_cli.services.agents.middleware.summarization import SummarizationMiddleware
        summary_mw = None
        if self._middleware:
            summary_mw = next(
                (m for m in self._middleware._middleware if isinstance(m, SummarizationMiddleware)),
                None,
            )
        if summary_mw is None:
            return False
        token_threshold = summary_mw.token_threshold
        if token_threshold <= 0 and self.config.token_budget > 0:
            token_threshold = int(self.config.token_budget * 0.85)
            summary_mw.token_threshold = token_threshold
        total_tokens = self._state.total_tokens if token_threshold > 0 else None
        if not summary_mw.should_summarize(self._messages, total_tokens=total_tokens):
            return False
        summary_prompt = getattr(summary_mw, '_summary_prompt', 'Summarize the following conversation:')
        summary_prompt_content = summary_prompt + "\n\n" + "\n".join(
            f"{m.get('role', '?')}: {str(m.get('content', ''))[:200]}"
            for m in self._messages[:-5]
        )
        await self._summarize(summary_mw, summary_prompt_content)
        return True

    async def _summarize(self, summary_mw: Any, summary_prompt_content: str) -> None:
        """Run the summarization exchange and swap in the rebuilt context."""
        try:
            summary_msg, _, _ = await self.parent_chat.streamer.chat(
                [{"role": "user", "content": summary_prompt_content}],
            )
            summary_text = getattr(summary_msg, "content", "") or ""
            self._summarized_archive.extend(list(self._messages))
            self._messages = summary_mw.build_summary_messages(
                self._messages, summary_text,
            )
            summary_mw.mark_summarized()
            if self.bus:
                await self.bus.push_log(
                    "info",
                    f"Context summarised ({len(summary_text)} chars, "
                    f"{len(self._summarized_archive)} raw messages archived)",
                )
        except Exception as exc:
            if self.bus:
                await self.bus.push_log("warn", f"Summarization failed: {exc}")

    async def _apply_tool_results(self, tool_calls: list[Any], iteration: int) -> None:
        """Execute a batch of tool calls and record the results."""
        if self.bus:
            await self.bus.push_log("info", f"Agent executing {len(tool_calls)} tool(s)...")
        await self._set_phase(
            "DELEGATING" if self._has_delegate_tool(tool_calls) else "EXECUTING",
            iteration=iteration,
        )
        tool_results = await self._execute_tool_calls(tool_calls)
        self._messages.extend(tool_results)
        self._tool_calls_made += len(tool_calls)

    # ------------------------------------------------------------------
    # Tool execution with HITL + permissions
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self, tool_calls: list[Any],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for call in tool_calls:
            name = call.function.name

            args, args_error = self._parse_args(call, name)
            if args is None:
                results.append(self._tool_result(call, name, args_error or ""))
                continue

            perm_err = self._perm_gate(name, args)
            if perm_err:
                results.append(self._tool_result(call, name, perm_err, raw=True))
                continue

            hitl_result = await self._hitl_gate(name, args, results)
            if hitl_result is not None:
                results.append(self._tool_result(call, name, hitl_result))
                continue

            result_text = await self._dispatch_tool(name, args)
            results.append(self._tool_result(call, name, result_text))
        return results

    def _parse_args(self, call: Any, name: str) -> tuple[dict[str, Any] | None, str | None]:
        """Parse tool arguments, recovering from common malformed-JSON wrapping."""
        try:
            return json.loads(call.function.arguments or "{}"), None
        except json.JSONDecodeError:
            # If the AI produces malformed JSON, try to recover by stripping
            # potential markdown formatting or trailing characters.
            raw_args = call.function.arguments or "{}"
            try:
                # Common issue: AI wraps JSON in ```json ... ```
                if "```" in raw_args:
                    raw_args = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", raw_args).strip()
                return json.loads(raw_args), None
            except Exception as exc:
                logger.warning("Agent %s: Malformed tool arguments for %s. %s. Raw: %s",
                               self.agent_id, name, exc, raw_args)
                return None, (
                    f"[invalid-args] Failed to parse arguments for '{name}': {exc}\n"
                    f"Raw input received: {raw_args[:500]}\n"
                    f"Please provide valid JSON arguments for this tool and retry."
                )

    def _perm_gate(self, name: str, args: dict[str, Any]) -> str | None:
        """Check filesystem permissions before executing."""
        if not self._perm_enforcer:
            return None
        return self._perm_enforcer.inspect_tool_args(name, args)

    async def _hitl_gate(
        self, name: str, args: dict[str, Any], results: list[dict[str, Any]],
    ) -> str | None:
        """Pause for human approval on gated tools; return result text or ``None``.

        Returns ``None`` when the tool is not gated, so normal dispatch runs.
        Raises ``AgentInterruptError`` when the resume yields no decisions,
        after recording the batch's partial results (H5).
        """
        if name not in self.config.interrupt_on:
            return None
        interrupt_cfg = _normalize_interrupt(self.config.interrupt_on[name])
        action_requests = [
            ActionRequest(
                name=name,
                args=args,
                allowed_decisions=interrupt_cfg.get("allowed_decisions", ["approve", "edit", "reject"]),
            )
        ]
        self._state.pending_interrupt = action_requests
        self._state.status = "waiting"
        if self.bus:
            await self.bus.push_interrupt([a.model_dump() for a in action_requests])

        await self._resume_event.wait()
        self._resume_event.clear()

        decisions = self._resume_decisions
        self._resume_decisions = None
        if not decisions:
            # Record partial results before the interrupt aborts the batch (H5)
            self._messages.extend(results)
            self._state.status = "failed"
            raise AgentInterruptError(action_requests)

        self._state.pending_interrupt = None
        self._state.status = "running"
        return await self._process_decisions(decisions[:1], action_requests)

    async def _dispatch_tool(self, name: str, args: dict[str, Any]) -> str:
        """Run middleware / virtual-backend / router dispatch for one tool."""
        # Middleware tool intercept
        if self._middleware:
            mw_handled, mw_result = await self._middleware.handle_tool(name, args)
            if mw_handled:
                return mw_result or ""

        # Virtual backend intercept
        if self._virtual_backend.can_handle(name):
            vb_result = await asyncio.to_thread(self._virtual_backend.handle_tool, name, args)
            if vb_result is not None:
                return vb_result

        if self.bus:
            await self.bus.push_tool_call(name, args, "running")

        try:
            result_text = await self.tool_router.call_tool(name, args)
        except Exception as exc:
            logger.warning("Agent %s: Tool call '%s' failed: %s", self.agent_id, name, exc)
            result_text = (
                f"[tool-error] Tool '{name}' raised an error: {exc}\n"
                f"Arguments: {json.dumps(args)[:500]}\n"
                f"Please fix the arguments and retry."
            )

        if self.bus:
            await self.bus.push_tool_call(name, args, "done", result_text)
        return result_text

    async def _process_decisions(
        self,
        decisions: list[ResumeDecision],
        pending: list[ActionRequest],
    ) -> str:
        """Process HITL decisions and return a result string to inject into messages."""
        parts: list[str] = []
        for req, decision in zip(pending, decisions):
            if decision.type == "approve":
                if self._virtual_backend.can_handle(req.name):
                    vb_result = await asyncio.to_thread(self._virtual_backend.handle_tool, req.name, req.args)
                    if vb_result is not None:
                        result_text = vb_result
                    else:
                        result_text = await self.tool_router.call_tool(req.name, req.args)
                else:
                    result_text = await self.tool_router.call_tool(req.name, req.args)
                parts.append(f"[approved] {req.name}: {result_text}")
            elif decision.type == "edit":
                if decision.edited_action:
                    edited_name = decision.edited_action.get("name", req.name)
                    edited_args = decision.edited_action.get("args", req.args)
                    result_text = await self.tool_router.call_tool(edited_name, edited_args)
                    parts.append(f"[edited] {edited_name}: {result_text}")
                else:
                    parts.append(f"[rejected] {req.name}: no edit provided, skipped")
            elif decision.type == "reject":
                msg = decision.message or "Rejected by user"
                parts.append(f"[rejected] {req.name}: {msg}")
            elif decision.type == "respond":
                msg = decision.message or ""
                parts.append(f"[responded] {req.name}: {msg}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Memory injection / persistence
    # ------------------------------------------------------------------

    async def _inject_memory(self) -> None:
        if not self.config.memory_files:
            return
        loaded = await asyncio.to_thread(self._memory.load_all, self.agent_id, self.config.memory_files)
        if not loaded:
            return
        block = "\n\n---\n".join(
            f"# Memory: {path}\n{content}"
            for path, content in loaded.items()
        )
        system_idx = None
        for i, m in enumerate(self._messages):
            if m.get("role") == "system":
                system_idx = i
                break
        note = f"\n\n## Persistent Memory\n{block}"
        if system_idx is not None:
            existing = self._messages[system_idx].get("content", "")
            if "## Persistent Memory" not in existing:
                self._messages[system_idx]["content"] = existing + note

    async def _persist_memory(self) -> None:
        if not self.config.memory_files:
            return
        for mp in self.config.memory_files:
            updated = self._memory_block_from_messages(mp)
            if updated is None:
                continue
            existing = await asyncio.to_thread(self._memory.read, self.agent_id, mp)
            if existing == updated:
                continue
            await asyncio.to_thread(self._memory.write, self.agent_id, mp, updated)
            logger.info("Persisted memory file %s for agent %s", mp, self.agent_id)

    def _find_memory_middleware(self) -> MemoryMiddleware | None:
        if self._middleware is None:
            return None
        for mw in self._middleware._middleware:
            if isinstance(mw, MemoryMiddleware):
                return mw
        return None

    def _memory_block_from_messages(self, mp: str) -> str | None:
        """Extract the current content of a memory file from the conversation.

        The injected memory block sits after the ``## Persistent Memory`` marker;
        the latest message carrying a copy of the block wins (e.g. the agent's
        final answer may carry an updated version of the file).
        """
        header = f"# Memory: {mp}"
        for msg in reversed(self._messages):
            content = msg.get("content", "")
            if not isinstance(content, str) or "## Persistent Memory" not in content:
                continue
            body = content.split("## Persistent Memory", 1)[1]
            for section in body.split("\n\n---\n"):
                lines = section.strip().splitlines()
                if lines and lines[0].strip() == header:
                    return "\n".join(lines[1:]).strip()
        return None

    # ------------------------------------------------------------------
    # Task lifecycle phases
    # ------------------------------------------------------------------

    async def _set_phase(self, phase: str, iteration: int | None = None) -> None:
        """Transition to a lifecycle phase, emitting on change only (coarse phases)."""
        if self._state.phase == phase:
            return
        now = datetime.now(UTC)
        self._state.phase = phase
        self._state.phase_transitions.append(
            PhaseTransition(phase=phase, timestamp=now, iteration=iteration),
        )
        self._state.last_active = now
        if self.bus:
            await self.bus.push_state(phase, self.agent_id, iteration=iteration)
            await self.bus.push_log("info", f"[{self.agent_id}] {phase}")

    @staticmethod
    def _has_delegate_tool(tool_calls: list[Any]) -> bool:
        for call in tool_calls:
            fn = getattr(call, "function", None)
            name = getattr(fn, "name", None)
            if name in ("delegate_task", "delegate_parallel"):
                return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_result(call: Any, name: str, content: str, raw: bool = False) -> dict[str, Any]:
        if raw:
            return {"role": "tool", "tool_call_id": call.id, "content": content}
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "content": f"<tool_result name=\"{name}\">\n{content}\n</tool_result>",
        }

    @staticmethod
    def _normalize_message(message: Any) -> dict[str, Any]:
        if hasattr(message, "model_dump"):
            return message.model_dump(exclude_unset=True)
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": getattr(message, "content", "") or "",
        }
        if hasattr(message, "tool_calls") and message.tool_calls:
            msg["tool_calls"] = message.tool_calls
        return msg
