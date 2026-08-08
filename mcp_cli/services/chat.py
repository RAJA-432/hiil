from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Literal

from mcp_cli.services.agents import (
    SUBAGENT_REGISTRY,
    AgentConfig,
    AgentRunner,
    classify,
)
from mcp_cli.services.builtin_tools import BuiltinTools
from mcp_cli.services.claude import _known_text_only_model, _known_vision_model
from mcp_cli.services.context_manager import ContextManager
from mcp_cli.services.discovery import DiscoveryTracker
from mcp_cli.services.document_injector import DocumentInjector
from mcp_cli.services.history import ChatHistoryManager
from mcp_cli.services.logging import get_logger
from mcp_cli.services.moderation import ModerationFilter
from mcp_cli.services.notification_bus import NotificationBus
from mcp_cli.services.prompt_budget import PromptBudget
from mcp_cli.services.rag import RagPipeline
from mcp_cli.services.registry import ToolRegistry
from mcp_cli.services.roots import RootsManager
from mcp_cli.services.server_manager import load_mcp_server
from mcp_cli.services.session import RecoveryHandler, SessionManager, TurnPipeline
from mcp_cli.services.streamer import Streamer
from mcp_cli.services.token_monitor import TokenMonitor
from mcp_cli.services.tool_runner import ToolRunner, _mcp_tool_to_openai
from mcp_cli.services.usage import UsageTracker
from mcp_cli.services.vector_store import VectorStore
from mcp_cli.services.verifier import Verifier

if TYPE_CHECKING:
    from setu_bridge import SetuBridge

logger = get_logger("chat")

_validation_error_count: int = 0


def new_session_id() -> str:
    """Generate a unique session id (timestamp + random suffix)."""
    import secrets
    from datetime import datetime
    return datetime.now().strftime("session_%Y%m%d_%H%M%S") + "_" + secrets.token_hex(3)


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
        discovery_guard: Literal["off", "warn", "block"] = "off",
        intent_routing: bool = False,
    ):
        self.clients = clients
        self.claude = claude_service
        self.session_id = session_id
        self.history = ChatHistoryManager()
        self.usage = UsageTracker()

        self.messages: list[dict[str, Any]] = self.history.load_session(session_id)
        self.tools_by_name: dict[str, dict[str, Any]] = {}
        self._openai_tools: list[dict[str, Any]] = []
        self.builtin_tools = BuiltinTools(self)
        self._register_builtin_tools()
        self._max_tool_iterations = max_tool_iterations

        self._roots = roots_manager or RootsManager()
        self._vector_store = VectorStore()
        self.streamer = Streamer(claude_service)
        self.context = ContextManager(claude_service, self._vector_store, max_context_tokens)
        self.rag = RagPipeline(claude_service, self._vector_store)
        self.doc_injector = DocumentInjector(doc_client)
        self.discovery_tracker = (
            DiscoveryTracker(discovery_guard) if discovery_guard != "off" else None
        )
        self.tool_runner = ToolRunner(
            self.tools_by_name,
            tool_timeout,
            roots_manager=self._roots,
            discovery=self.discovery_tracker,
        )
        self.discovery_guard = discovery_guard
        self.intent_routing = intent_routing
        self.registry = ToolRegistry()
        self._auto_index_task: asyncio.Task | None = None
        self.response_format: dict[str, Any] | None = None
        self._correction_attempts = 0
        self.MAX_CORRECTION_ATTEMPTS = 2

        self.enable_verification = enable_verification
        self.verifier_model = verifier_model
        self.enable_moderation = enable_moderation
        self.moderation_deny_list = moderation_deny_list

        self.token_monitor = TokenMonitor()
        self.prompt_budget = PromptBudget(max_tokens=4096)

        self.verifier: Verifier | None = None
        if self.enable_verification and self.claude is not None:
            self.verifier = Verifier(self.claude, model=self.verifier_model)
        self.moderation: ModerationFilter | None = None
        if self.enable_moderation:
            self.moderation = ModerationFilter(enabled=True, deny_list=self.moderation_deny_list)

        # Agent spawning
        self.agents: dict[str, AgentRunner] = {}
        self._recovery_attempted = False
        self._session_manager = SessionManager(self)

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
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Re-register builtin tools after the MCP registry is (re)built."""
        self.builtin_tools.register(self.tools_by_name)
        self._openai_tools = [v["openai"] for v in self.tools_by_name.values()]

    async def _push_state(self, phase: str, iteration: int | None = None) -> None:
        """Emit a task-lifecycle phase for the orchestrator chat on the active bus."""
        bus = getattr(self, "_active_bus", None)
        if bus is None:
            return
        await bus.push_state(phase, self.session_id, iteration=iteration)
        await bus.push_log("info", f"[{self.session_id}] {phase}")

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
        return self._session_manager.new_session()

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
        return self._session_manager.export_transcript()

    async def switch_session(self, session_id: str) -> None:
        await self._session_manager.switch(session_id)

    async def rename_session(self, name: str) -> bool:
        return await self._session_manager.rename(name)

    async def fork_session(self, session_id: str) -> tuple[int, str]:
        return await self._session_manager.fork(session_id)

    async def undo_session(self, count: int = 2) -> int:
        return await self._session_manager.undo(count)

    async def load_session(self, session_id: str) -> list[dict[str, Any]]:
        return await self._session_manager.load_session(session_id)

    async def list_sessions(self) -> list[str]:
        return await self._session_manager.list_sessions()

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
        if _known_vision_model(model_lower):
            return True
        if _known_text_only_model(model_lower):
            return False
        return True

    async def _can_process_images(self) -> bool:
        """Check whether the active model can process images."""
        caps = await self.claude.model_capabilities(self.claude.model)
        if caps:
            return "vision" in caps
        return self._is_vision_model(self.claude.model)

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
        self._active_bus = bus
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

        if getattr(self, "intent_routing", False):
            agent_name = await classify(user_input, llm_client=self.claude)
            agent_config = SUBAGENT_REGISTRY.get(agent_name) if agent_name else None
            if agent_config is not None:
                if bus:
                    await bus.push_log("info", f"Routing request to '{agent_config.name}' agent.")
                runner = self.spawn_agent(agent_config, bus=bus)
                result = await runner.run(user_input)
                if bus:
                    await bus.push_done()
                return result.output or f"Agent '{agent_config.name}' returned no output."

        recovery = RecoveryHandler(
            self.streamer,
            self.usage,
            self.claude.model,
            self.session_id,
            bus=bus,
            max_correction_attempts=self.MAX_CORRECTION_ATTEMPTS,
        )
        pipeline = TurnPipeline(
            claude=self.claude,
            streamer=self.streamer,
            context=self.context,
            rag=self.rag,
            doc_injector=self.doc_injector,
            tool_runner=self.tool_runner,
            registry=self.registry,
            usage=self.usage,
            history=self.history,
            moderation=self.moderation,
            verifier=self.verifier,
            bus=bus,
            max_tool_iterations=self._max_tool_iterations,
            messages=self.messages,
            session_id=self.session_id,
            tools_by_name=self.tools_by_name,
            openai_tools=self._openai_tools,
            default_response_format=self.response_format,
            recovery=recovery,
            push_state=self._push_state,
            validate_output=self._validate_output,
            auto_index_wrapper=self._auto_index_wrapper,
            can_process_images=self._can_process_images,
            token_monitor=getattr(self, "token_monitor", None),
            prompt_budget=getattr(self, "prompt_budget", None),
        )
        try:
            return await pipeline.run(
                user_input,
                images=images,
                on_tool_event=on_tool_event,
                on_chunk=on_chunk,
                on_approval=on_approval,
                response_format=response_format,
                bus=bus,
            )
        finally:
            self.messages = pipeline.messages
            self._auto_index_task = pipeline.auto_index_task
