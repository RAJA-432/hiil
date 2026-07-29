from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from mcp_cli.services.agents import AgentConfig, AgentRunner
from mcp_cli.services.context_manager import ContextManager
from mcp_cli.services.document_injector import DocumentInjector
from mcp_cli.services.history import ChatHistoryManager
from mcp_cli.services.logging import get_logger
from mcp_cli.services.notification_bus import NotificationBus
from mcp_cli.services.rag import RagPipeline
from mcp_cli.services.roots import RootsManager
from mcp_cli.services.server_manager import load_mcp_server
from mcp_cli.services.streamer import Streamer
from mcp_cli.services.tool_runner import ToolRunner, _mcp_tool_to_openai
from mcp_cli.services.usage import UsageTracker, count_tokens
from mcp_cli.services.vector_store import VectorStore

if TYPE_CHECKING:
    from setu_bridge import SetuBridge

logger = get_logger("chat")


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
        api_ctx = await self.context.fetch_model_context(self.claude.model)
        self.context.max_context_tokens = min(self.context.max_context_tokens, int(api_ctx * 0.9))
        logger.info("model context limit: %s, effective budget: %s", api_ctx, self.context.max_context_tokens)

    def refresh_system_prompt(self) -> None:
        prompt = self.claude.system_prompt()
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

    async def send(
        self,
        user_input: str,
        on_tool_event: Any = None,
        on_chunk: Any = None,
        on_approval: Any = None,
        notification_bus: NotificationBus | None = None,
    ) -> str:
        bus = notification_bus
        user_input = self._sanitize_input(user_input)

        if bus:
            await bus.push_log("info", "Processing your request...")

        augmented = await self.doc_injector.resolve(user_input)

        try:
            rag_results = await self.rag.retrieve(user_input, top_k=3, min_score=0.25)
            if rag_results:
                ctx = self.rag.format_context(rag_results)
                augmented = (
                    f"Relevant knowledge base context:\n{ctx}\n\n"
                    f"User question: {augmented}"
                )
                if bus:
                    bus.push_rag(rag_results)
        except Exception:
            logger.warning("RAG retrieval failed, continuing without knowledge base context")

        self._auto_index_task = asyncio.create_task(
            self._auto_index_wrapper(user_input), name="auto_index"
        )
        self.messages.append({"role": "user", "content": augmented})
        await self.history.async_save_message(self.session_id, "user", augmented)
        tools = self._openai_tools if self._openai_tools else None
        tools_tokens = count_tokens(json.dumps(tools), self.claude.model) if tools else 0
        self.messages = self.context.trim(self.messages, tools_tokens)
        iterations = 0
        while True:
            iterations += 1
            if iterations > self._max_tool_iterations:
                if bus:
                    await bus.push_log("warn", f"Stopped after {self._max_tool_iterations} tool iterations.")
                return f"[stopped] Maximum tool calls ({self._max_tool_iterations}) reached."

            if bus:
                await bus.push_log("info", f"Calling LLM (iteration {iterations})...")

            message, input_tokens, output_tokens = await self.streamer.chat(
                self.messages, tools=tools, on_chunk=on_chunk,
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
                if bus:
                    await bus.push_log("info", "Response complete.")
                    await bus.push_done()
                return message.content or ""

            if bus:
                await bus.push_log("info", f"Executing {len(tool_calls)} tool(s)...")

            tool_results = await self.tool_runner.execute_tool_calls(
                tool_calls,
                on_tool_event=on_tool_event,
                on_approval=on_approval,
            )
            self.messages.extend(tool_results)
            self.messages = self.context.trim(self.messages, tools_tokens)
