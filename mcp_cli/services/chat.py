from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from mcp_cli.services.agents import AgentConfig, AgentRunner
from mcp_cli.services.context_manager import ContextManager
from mcp_cli.services.document_injector import DocumentInjector
from mcp_cli.services.history import ChatHistoryManager
from mcp_cli.services.logging import get_logger
from mcp_cli.services.moderation import ModerationFilter
from mcp_cli.services.notification_bus import NotificationBus
from mcp_cli.services.rag import RagPipeline
from mcp_cli.services.roots import RootsManager
from mcp_cli.services.server_manager import load_mcp_server
from mcp_cli.services.streamer import Streamer
from mcp_cli.services.tool_runner import ToolRunner, _mcp_tool_to_openai
from mcp_cli.services.usage import UsageTracker, count_tokens
from mcp_cli.services.vector_store import VectorStore
from mcp_cli.services.verifier import Verifier

if TYPE_CHECKING:
    from setu_bridge import SetuBridge

logger = get_logger("chat")

_validation_error_count: int = 0


def _inc_validation_error() -> None:
    global _validation_error_count
    _validation_error_count += 1


def _get_validation_error_count() -> int:
    return _validation_error_count


class CliChat:
    def __init__(
        self,
        doc_client: SetuBridge | None,
        clients: dict[str, SetuBridge],
        claude_service: Any,
        max_tool_iterations: int = 10,
        tool_timeout: float = 30.0,
        session_id: str = "default",
        max_context_tokens: int = 200_000,
        roots_manager: RootsManager | None = None,
        *,
        enable_verification: bool = False,
        verifier_model: str | None = None,
        enable_moderation: bool = False,
        moderation_deny_list: list[str] | None = None,
    ):
        self.clients = clients
        self.claude = claude_service
        self.session_id = session_id
        self.history = ChatHistoryManager()
        self.usage = UsageTracker()

        self.messages: list[dict[str, Any]] = self.history.load_session(session_id)
        self.tools_by_name: dict[str, dict[str, Any]] = {}
        self._openai_tools: list[dict[str, Any]] = []
        self._max_tool_iterations = max_tool_iterations

        self._roots = roots_manager or RootsManager()
        self._vector_store = VectorStore()
        self.streamer = Streamer(claude_service)
        self.context = ContextManager(claude_service, self._vector_store, max_context_tokens)
        self.rag = RagPipeline(claude_service, self._vector_store)
        self.doc_injector = DocumentInjector(doc_client)
        self.tool_runner = ToolRunner(self.tools_by_name, tool_timeout, roots_manager=self._roots)
        self._auto_index_task: asyncio.Task | None = None
        self.response_format: dict[str, Any] | None = None
        self._correction_attempts = 0
        self.MAX_CORRECTION_ATTEMPTS = 2

        self.enable_verification = enable_verification
        self.verifier_model = verifier_model
        self.enable_moderation = enable_moderation
        self.moderation_deny_list = moderation_deny_list

        self.verifier: Verifier | None = None
        if self.enable_verification and self.claude is not None:
            self.verifier = Verifier(self.claude, model=self.verifier_model)
        self.moderation: ModerationFilter | None = None
        if self.enable_moderation:
            self.moderation = ModerationFilter(enabled=True, deny_list=self.moderation_deny_list)

        # Agent spawning
        self.agents: dict[str, AgentRunner] = {}

    async def close(self):
        if self._auto_index_task is not None and not self._auto_index_task.done():
            self._auto_index_task.cancel()
        await self.claude.shutdown()
        self.history.close()
        self.usage.close()
        self._vector_store.close()

    @property
    def doc_client(self):
        return self.doc_injector.doc_client

    @doc_client.setter
    def doc_client(self, value):
        self.doc_injector.doc_client = value

    @property
    def vector_store(self):
        return self._vector_store

    @vector_store.setter
    def vector_store(self, value):
        self._vector_store = value
        self.context.vector_store = value

    @property
    def doc_ids(self) -> list[str]:
        return self.doc_injector.doc_ids

    @doc_ids.setter
    def doc_ids(self, value: list[str]) -> None:
        self.doc_injector.doc_ids = value

    async def _resolve_docs(self, text: str) -> str:
        return await self.doc_injector.resolve(text)

    async def _auto_index_wrapper(self, text: str) -> None:
        try:
            await self.context.auto_index(text)
        except Exception as exc:
            logger.warning("auto_index failed: %s", exc)

    def _trim_messages(self) -> None:
        self.messages = self.context.trim(self.messages)

    async def _auto_index(self, text: str, namespace: str = "messages") -> None:
        await self.context.auto_index(text, namespace=namespace)

    async def refresh_tools(self):
        self.tools_by_name.clear()
        all_clients: dict[str, SetuBridge | None] = {
            "doc_client": self.doc_client,
            **self.clients,
        }

        async def _fetch(client_id: str, client: SetuBridge | None):
            if client is None:
                return
            try:
                tools = await client.list_tools()
                for tool in tools:
                    self.tools_by_name[tool.name] = {
                        "client": client,
                        "openai": _mcp_tool_to_openai(tool),
                    }
            except Exception as exc:
                logger.warning("could not refresh tools from %s: %s", client_id, exc)

        await asyncio.gather(*(
            _fetch(cid, c) for cid, c in all_clients.items()
        ))
        self._openai_tools = [v["openai"] for v in self.tools_by_name.values()]

    async def add_server(self, server_id: str, script: str) -> str:
        if server_id in self.clients:
            return f"Server '{server_id}' is already loaded."
        try:
            client = await load_mcp_server(server_id, script)
            self.clients[server_id] = client
            await self.refresh_tools()
            return f"Server '{server_id}' loaded successfully from {script}."
        except Exception as exc:
            return f"Failed to load server '{server_id}': {exc}"

    async def remove_server(self, server_id: str) -> str:
        if server_id == "doc_client":
            return "Cannot unload the primary document server."
        if server_id not in self.clients:
            return f"Server '{server_id}' not found."
        try:
            client = self.clients.pop(server_id)
            await client.cleanup()
            await self.refresh_tools()
            return f"Server '{server_id}' unloaded successfully."
        except Exception as exc:
            return f"Error unloading server '{server_id}': {exc}"

    async def reload_server(self, server_id: str, script: str) -> str:
        await self.remove_server(server_id)
        return await self.add_server(server_id, script)

    async def initialize(self) -> None:
        await self.refresh_tools()
        await self.doc_injector.initialize()
        await self.refresh_system_prompt()
        api_ctx = await self.context.fetch_model_context(self.claude.model)
        if api_ctx is not None:
            self.context.max_context_tokens = min(self.context.max_context_tokens, int(api_ctx * 0.9))
        logger.info("model context limit: %s, effective budget: %s", api_ctx, self.context.max_context_tokens)

    async def _fetch_mcp_format_instructions(self) -> str | None:
        parts: list[str] = []
        all_clients: dict[str, SetuBridge | None] = {
            "doc_client": self.doc_client,
            **self.clients,
        }
        for cid, client in all_clients.items():
            if client is None:
                continue
            try:
                prompts = await client.list_prompts()
                for p in prompts:
                    if p.name and "format" in p.name.lower():
                        result = await client.get_prompt(p.name, {})
                        for msg in result:
                            if hasattr(msg.content, "text"):
                                parts.append(msg.content.text)
                            elif isinstance(msg.content, dict):
                                parts.append(msg.content.get("text", ""))
            except Exception:
                logger.debug("no prompts from %s (expected for most servers)", cid)
        return "\n\n".join(parts) if parts else None

    async def refresh_system_prompt(self) -> None:
        fmt = await self._fetch_mcp_format_instructions()
        prompt = self.claude.system_prompt(format_instructions=fmt)
        for i, m in enumerate(self.messages):
            if m.get("role") == "system":
                self.messages[i] = {"role": "system", "content": prompt}
                return
        self.messages.insert(0, {"role": "system", "content": prompt})

    @staticmethod
    def _sanitize_input(text: str) -> str:
        text = text.replace("\0", "")
        stripped = text.strip().lower()
        stripped = stripped.replace("\u200b", "").replace("\ufeff", "")
        stripped = " ".join(stripped.split())
        blocklist = [
            "ignore previous instructions",
            "ignore all instructions",
            "ignore all previous",
            "forget everything",
            "you are now",
            "you are not",
            "disregard",
            "system override",
            "new system prompt",
            "override system",
            "you are free",
            "you have been",
        ]
        for pattern in blocklist:
            if pattern in stripped:
                raise ValueError(f"Message blocked: {pattern!r} — prompt injection pattern detected")
        return text

    def get_last_assistant_message(self) -> str | None:
        for m in reversed(self.messages):
            if m.get("role") == "assistant" and m.get("content"):
                return m["content"]
        return None

    def new_session(self) -> str:
        from datetime import datetime
        sid = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.session_id = sid
        self.messages = []
        return sid

    def get_status(self) -> dict[str, Any]:
        info = self.claude.status_info() if hasattr(self.claude, "status_info") else {}
        return {
            "session": self.session_id,
            "messages": len(self.messages),
            "servers": list(self.clients.keys()),
            "model": info.get("model", self.claude.model),
            "provider": info.get("provider", self.claude.provider),
            "tools": len(self.tools_by_name),
        }

    def export_transcript(self) -> str:
        lines = []
        for m in self.messages:
            role = m.get("role", "?")
            content = m.get("content", "")
            lines.append(f"[{role}]\n{content}\n")
        return "\n".join(lines)

    async def semantic_search(self, query: str, namespace: str = "messages", limit: int = 5) -> list[dict[str, Any]]:
        return await self.context.semantic_search(query, namespace=namespace, limit=limit)

    async def call_tool_by_name(self, name: str, args: dict[str, Any]) -> str:
        return await self.tool_runner.call_tool(name, args)

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    def spawn_agent(self, config: AgentConfig, bus: NotificationBus | None = None) -> AgentRunner:
        """Create a new agent with filtered tool access based on ``config.capabilities``."""
        runner = AgentRunner(config=config, parent_chat=self, bus=bus)
        self.agents[runner.agent_id] = runner
        logger.info("Spawned agent %s (%s) with capabilities %s", runner.agent_id, config.name, config.capabilities)
        return runner

    async def parallel_spawn(
        self,
        agents: list[tuple[AgentConfig, str]],
    ) -> list[tuple[str, Any]]:
        """Spawn multiple agents in parallel and run each with its own task input.

        Each tuple is ``(config, task_input)``. Returns ``[(agent_id, AgentResult), ...]``
        in the same order as the input list.

        Used by playbooks that require concurrent research (e.g. newsletter
        genre research fans out one ``genre-researcher`` per genre).
        """
        runners: list[AgentRunner] = []
        for config, task_input in agents:
            runner = self.spawn_agent(config)
            runners.append(runner)

        async def _run(runner: AgentRunner, task: str) -> tuple[str, Any]:
            result = await runner.run(task)
            return (runner.agent_id, result)

        return await asyncio.gather(*(
            _run(r, t) for r, (_, t) in zip(runners, agents)
        ))

    def get_agent(self, agent_id: str) -> AgentRunner | None:
        return self.agents.get(agent_id)

    async def stop_agent(self, agent_id: str) -> bool:
        runner = self.agents.get(agent_id)
        if runner is None:
            return False
        await runner.stop()
        return True

    def list_roots(self) -> list[dict[str, Any]]:
        return self._roots.list_roots()

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": a.agent_id,
                "name": a.config.name,
                "role": a.config.role,
                "capabilities": a.config.capabilities,
                "status": a.state.status,
            }
            for a in self.agents.values()
        ]

    def _validate_output(self, content: str) -> tuple[bool, str | None]:
        if not self.response_format:
            return True, None
        schema = self.response_format.get("json_schema", {}).get("schema")
        if not schema:
            return True, None
        try:
            from jsonschema import Draft7Validator, ValidationError
            data = json.loads(content)
            Draft7Validator(schema).validate(data)
            return True, None
        except (json.JSONDecodeError, ImportError):
            return True, None
        except ValidationError as e:
            return False, str(e)

    @staticmethod
    def _is_vision_model(model: str) -> bool:
        model_lower = model.lower()
        vision_keywords = ["vision", "gpt-4o", "gpt-4-turbo", "claude-3", "claude-4", "gemini-1.5", "gemini-2.0", "llava", "cogvlm", "qwen-vl", "internvl"]
        if any(kw in model_lower for kw in vision_keywords):
            return True
        non_vision = ["gemma2", "gemma-2", "deepseek", "llama-3.1", "mixtral", "mistral"]
        if any(nm in model_lower for nm in non_vision):
            return False
        return True

    async def _can_process_images(self) -> bool:
        """Check whether the active model can process images."""
        caps = await self.claude.model_capabilities(self.claude.model)
        if caps:
            return "vision" in caps
        return self._is_vision_model(self.claude.model)

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

    async def _correction_retry(
        self,
        answer: str,
        user_input: str,
        issues: list[str],
        bus: NotificationBus | None,
    ) -> str:
        if self._correction_attempts >= self.MAX_CORRECTION_ATTEMPTS:
            return ""
        self._correction_attempts += 1
        issue_text = "\n".join(f"- {issue}" for issue in issues)
        correction = (
            "Your previous response was flagged by a verification pass. "
            f"Address the following issues:\n{issue_text}"
        )
        retry_messages = [*self.messages, {"role": "user", "content": correction}]
        try:
            message, input_tokens, output_tokens = await self.streamer.chat(
                retry_messages,
                tools=self._openai_tools if self._openai_tools else None,
            )
            await self.usage.async_record(self.claude.model, input_tokens, output_tokens, self.session_id)
            return message.content or ""
        except Exception as exc:
            logger.warning("verifier correction retry failed, returning original answer: %s", exc)
            return ""

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
                retried = await self._correction_retry(answer, user_input, verdict.issues, bus)
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

    async def send(
        self,
        user_input: str,
        images: list[str] | None = None,
        on_tool_event: Any = None,
        on_chunk: Any = None,
        on_approval: Any = None,
        notification_bus: NotificationBus | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        bus = notification_bus
        self._correction_attempts = 0
        user_input = self._sanitize_input(user_input)

        if self.moderation is not None:
            try:
                ok, reason = self.moderation.check_input(user_input)
            except Exception:
                ok, reason = True, ""
            if not ok:
                if bus:
                    await bus.push_log("warn", f"Input blocked by moderation ({reason}).")
                return f"[blocked] Your message was flagged by moderation ({reason})."

        if bus:
            await bus.push_log("info", "Processing your request...")

        augmented = await self.doc_injector.resolve(user_input)

        rag_context = ""
        try:
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

        self._auto_index_task = asyncio.create_task(
            self._auto_index_wrapper(user_input), name="auto_index"
        )

        # OCR fallback for non-vision models
        if images and not await self._can_process_images():
            from mcp_cli.services.ocr import extract_text_from_data_url, is_available
            if is_available():
                ocr_texts = []
                for img_url in images:
                    text = extract_text_from_data_url(img_url)
                    if text:
                        ocr_texts.append(text)
                if ocr_texts:
                    ocr_context = "\n\n[OCR text extracted from image(s)]:\n" + "\n---\n".join(ocr_texts)
                    augmented = augmented + ocr_context
                    if bus:
                        await bus.push_log("info", f"OCR extracted text from {len(ocr_texts)} image(s)")
                elif bus:
                    await bus.push_log("warn", "OCR available but no text could be extracted from image(s)")
            else:
                if bus:
                    await bus.push_log("warn", "OCR libraries not installed (pip install Pillow pytesseract). Cannot process images with this model.")
            images = None  # Don't send images to non-vision model

        if images:
            content: list[dict] = [{"type": "text", "text": augmented}]
            for img_url in images:
                content.append({"type": "image_url", "image_url": {"url": img_url}})
            self.messages.append({"role": "user", "content": content})
            save_content = json.dumps(content)
        else:
            self.messages.append({"role": "user", "content": augmented})
            save_content = augmented
        await self.history.async_save_message(self.session_id, "user", save_content)
        tools = self._openai_tools if self._openai_tools else None
        tools_tokens = count_tokens(json.dumps(tools), self.claude.model) if tools else 0
        self.messages = self.context.trim(self.messages, tools_tokens)
        iterations = 0
        tool_used = False
        tool_events: list[str] = []
        while True:
            iterations += 1
            if iterations > self._max_tool_iterations:
                if bus:
                    await bus.push_log("warn", f"Stopped after {self._max_tool_iterations} tool iterations.")
                return await self._moderate_output(
                    f"[stopped] Maximum tool calls ({self._max_tool_iterations}) reached.", bus,
                )

            if bus:
                await bus.push_log("info", f"Calling LLM (iteration {iterations})...")

            fmt = response_format or self.response_format
            message, input_tokens, output_tokens = await self.streamer.chat(
                self.messages, tools=tools, on_chunk=on_chunk, response_format=fmt,
            )
            await self.usage.async_record(self.claude.model, input_tokens, output_tokens, self.session_id)

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
            if not tool_calls:
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
                    return final_answer

                logger.warning("output validation failed: %s", err)
                _inc_validation_error()
                logger.info(
                    "refinement_audit skill=%s valid=%s error=%s",
                    (self.response_format or {}).get("json_schema", {}).get("name", "unknown"),
                    is_valid,
                    err,
                )

                if self._correction_attempts < self.MAX_CORRECTION_ATTEMPTS:
                    self._correction_attempts += 1
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
                return final_answer

            if bus:
                await bus.push_log("info", f"Executing {len(tool_calls)} tool(s)...")

            tool_used = True
            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                name = getattr(fn, "name", None) or getattr(tc, "name", "") or "tool"
                args = getattr(fn, "arguments", None) or ""
                tool_events.append(f"{name}({args})" if args else name)

            tool_results = await self.tool_runner.execute_tool_calls(
                tool_calls,
                on_tool_event=on_tool_event,
                on_approval=on_approval,
            )
            self.messages.extend(tool_results)
            self.messages = self.context.trim(self.messages, tools_tokens)
