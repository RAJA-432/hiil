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
from mcp_cli.services.agents.middleware import MiddlewarePipeline
from mcp_cli.services.agents.models import (
    AgentConfig,
    AgentResult,
    AgentState,
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

        # Build the tool router from parent's tool registry
        self.tool_router = ToolRouter(
            tools_by_name=parent_chat.tools_by_name,
            clients=parent_chat.clients,
            capabilities=config.capabilities,
        )

        # Permission enforcer for file operations
        self._perm_enforcer = PermissionEnforcer(config.permissions) if config.permissions else None

        # Virtual backend (in-memory filesystem; never touches real disk by default)
        self._virtual_backend = VirtualBackend()

        # Memory store
        self._memory = _get_memory_store()
        self._memory_snapshot: dict[str, int] = {}

        # Middleware pipeline
        self._middleware = MiddlewarePipeline(config.middleware) if config.middleware else None

        # HITL resume synchronisation
        self._resume_event = asyncio.Event()
        self._resume_decisions: list[ResumeDecision] | None = None

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

        start = time.monotonic()
        output = ""
        error: str | None = None
        final_status: Literal["completed", "failed", "waiting"] = "completed"

        try:
            output = await asyncio.wait_for(
                self._execute_loop(task_input),
                timeout=self.config.timeout_seconds,
            )
        except AgentInterruptError as exc:
            self._state.pending_interrupt = exc.action_requests
            self._state.status = "waiting"
            final_status = "waiting"
            error = str(exc)
            output = ""
        except TimeoutError:
            error = f"Agent timed out after {self.config.timeout_seconds}s"
            final_status = "failed"
            logger.warning("Agent %s: %s", self.agent_id, error)
        except Exception as exc:
            error = str(exc)
            final_status = "failed"
            logger.exception("Agent %s failed: %s", self.agent_id, error)

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

        if self.bus and final_status != "waiting":
            await self.bus.push_done()

        return result

    async def resume(self, decisions: list[ResumeDecision]) -> AgentResult:
        """Resume execution after a human-in-the-loop pause."""
        pending = self._state.pending_interrupt
        if not pending:
            raise RuntimeError("No pending interrupt to resume from")

        self._resume_decisions = decisions
        self._state.pending_interrupt = None
        self._resume_event.set()

        start = time.monotonic()
        output = ""
        error: str | None = None
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
            error = str(exc)
            output = ""
        except TimeoutError:
            error = f"Agent timed out after {self.config.timeout_seconds}s"
            final_status = "failed"
        except Exception as exc:
            error = str(exc)
            final_status = "failed"

        elapsed = time.monotonic() - start
        self._state.last_active = datetime.now(UTC)
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
            self._inject_memory()

            # Middleware: before_run
            if self._middleware:
                self._messages = self._middleware.before_run(self._messages)

            system_prompt = self.config.system_prompt or f"You are a {self.config.role} assistant."
            if not self._messages or self._messages[0].get("role") != "system":
                self._messages.insert(0, {"role": "system", "content": system_prompt})
            self._messages.append({"role": "user", "content": task_input})

        # Merge MCP tools with middleware extra tools
        tools = list(self.tool_router.openai_tools or [])
        if self._middleware:
            tools.extend(self._middleware.get_extra_tools())
        tools_: list[dict[str, Any]] | None = tools or None

        for iteration in range(1, self.config.max_iterations + 1):
            if self.bus:
                await self.bus.push_log("info", f"LLM call (iteration {iteration})...")

            message, input_tokens, output_tokens = await self.parent_chat.streamer.chat(
                self._messages, tools=tools_,
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

            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                self._persist_memory()
                if self.bus:
                    await self.bus.push_log("info", "Agent response complete.")
                return message.content or ""

            # Check summarization middleware
            from mcp_cli.services.agents.summarization import SummarizationMiddleware
            summary_mw = next(
                (m for m in (self._middleware._middleware if self._middleware else [])
                 if isinstance(m, SummarizationMiddleware)),
                None,
            )
            if summary_mw and summary_mw.should_summarize(self._messages):
                summary_prompt_content = summary_mw._summary_prompt + "\n\n" + "\n".join(
                    f"{m.get('role', '?')}: {str(m.get('content', ''))[:200]}"
                    for m in self._messages[:-5]
                )
                try:
                    summary_msg, _, _ = await self.parent_chat.streamer.chat(
                        [{"role": "user", "content": summary_prompt_content}],
                    )
                    summary_text = getattr(summary_msg, "content", "") or ""
                    self._messages = summary_mw.build_summary_messages(
                        self._messages, summary_text,
                    )
                    if self.bus:
                        await self.bus.push_log("info", f"Context summarised ({len(summary_text)} chars)")
                except Exception as exc:
                    if self.bus:
                        await self.bus.push_log("warn", f"Summarization failed: {exc}")

            if self.bus:
                await self.bus.push_log("info", f"Agent executing {len(tool_calls)} tool(s)...")

            tool_results = await self._execute_tool_calls(tool_calls)
            self._messages.extend(tool_results)
            self._tool_calls_made += len(tool_calls)

        self._persist_memory()
        return f"[stopped] Max iterations ({self.config.max_iterations}) reached."

    # ------------------------------------------------------------------
    # Tool execution with HITL + permissions
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self, tool_calls: list[Any],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                # If the AI produces malformed JSON, try to recover by stripping
                # potential markdown formatting or trailing characters.
                raw_args = call.function.arguments or "{}"
                try:
                    # Common issue: AI wraps JSON in ```json ... ```
                    if "```" in raw_args:
                        raw_args = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", raw_args).strip()
                    args = json.loads(raw_args)
                except Exception:
                    logger.warning("Agent %s: Malformed tool arguments for %s. Using empty args. Raw: %s",
                                   self.agent_id, name, raw_args)
                    args = {}

            # Check filesystem permissions before executing
            if self._perm_enforcer:
                perm_err = self._perm_enforcer.inspect_tool_args(name, args)
                if perm_err:
                    results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": perm_err,
                    })
                    continue

            # Check HITL gate
            if name in self.config.interrupt_on:
                interrupt_cfg = _normalize_interrupt(self.config.interrupt_on[name])
                action_requests = [
                    ActionRequest(
                        name=name,
                        args=args,
                        allowed_decisions=interrupt_cfg.get("allowed_decisions", ["approve", "edit", "reject"]),
                    )
                ]
                raise AgentInterruptError(action_requests)

            # Middleware tool intercept
            if self._middleware:
                mw_handled, mw_result = await self._middleware.handle_tool(name, args)
                if mw_handled:
                    results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": f"<tool_result name=\"{name}\">\n{mw_result}\n</tool_result>",
                    })
                    continue

            # Virtual backend intercept
            if self._virtual_backend.can_handle(name):
                vb_result = self._virtual_backend.handle_tool(name, args)
                if vb_result is not None:
                    results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": f"<tool_result name=\"{name}\">\n{vb_result}\n</tool_result>",
                    })
                    continue

            if self.bus:
                await self.bus.push_tool_call(name, args, "running")

            result_text = await self.tool_router.call_tool(name, args)

            if self.bus:
                await self.bus.push_tool_call(name, args, "done", result_text)

            results.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": f"<tool_result name=\"{name}\">\n{result_text}\n</tool_result>",
            })
        return results

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
                    vb_result = self._virtual_backend.handle_tool(req.name, req.args)
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

    def _inject_memory(self) -> None:
        if not self.config.memory_files:
            return
        loaded = self._memory.load_all(self.agent_id, self.config.memory_files)
        self._memory_snapshot = self._memory.snapshot_hashes(self.agent_id, self.config.memory_files)
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

    def _persist_memory(self) -> None:
        if not self.config.memory_files:
            return
        for mp in self.config.memory_files:
            new_hash = self._memory.snapshot_hashes(self.agent_id, [mp]).get(mp, 0)
            old_hash = self._memory_snapshot.get(mp, 0)
            if new_hash != old_hash:
                content = self._memory.read(self.agent_id, mp)
                if content is not None:
                    logger.info("Memory file %s unchanged (snapshot match)", mp)
                continue
            for msg in self._messages:
                content = msg.get("content", "")
                if isinstance(content, str) and f"Memory: {mp}" in content:
                    lines = content.split("\n## Persistent Memory", 1)[0]
                    self._memory.write(self.agent_id, mp, lines)
                    logger.info("Persisted memory file %s for agent %s", mp, self.agent_id)
                    break

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
