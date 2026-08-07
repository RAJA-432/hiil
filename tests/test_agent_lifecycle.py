from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from mcp_cli.services.agents.models import AgentConfig, AgentState, PhaseTransition
from mcp_cli.services.agents.runner import AgentRunner
from mcp_cli.services.chat import CliChat
from mcp_cli.services.notification_bus import NotificationBus


class _FakeBus:
    def __init__(self) -> None:
        self.states: list[dict[str, Any]] = []
        self.logs: list[tuple[str, str]] = []
        self.done_calls = 0

    async def push_state(self, phase: str, agent_id: str, iteration: int | None = None) -> None:
        self.states.append({"phase": phase, "agent_id": agent_id, "iteration": iteration})

    async def push_log(self, level: str, message: str, source: str = "") -> None:
        self.logs.append((level, message))

    async def push_done(self) -> None:
        self.done_calls += 1

    async def push_tool_call(self, name: str, args: dict, status: str, result: str = "") -> None:
        pass


class _FakeClient:
    async def call_tool(self, name: str, args: dict) -> str:
        return f"result from {name}"


class _FakeStreamer:
    def __init__(self, responses: list[tuple[Any, int, int]]) -> None:
        self._responses = list(responses)

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        message, input_tokens, output_tokens = self._responses.pop(0)
        return message, input_tokens, output_tokens


class _FakeParent:
    def __init__(self, streamer: _FakeStreamer) -> None:
        self.streamer = streamer
        client = _FakeClient()
        self.clients = {"noop": client}
        self.tools_by_name = {
            "noop": {
                "client": client,
                "openai": {
                    "type": "function",
                    "function": {
                        "name": "noop",
                        "description": "noop tool",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            }
        }


def _tool_message(name: str = "noop") -> SimpleNamespace:
    return SimpleNamespace(
        content="",
        tool_calls=[SimpleNamespace(id="call_1", function=SimpleNamespace(name=name, arguments="{}"))],
    )


def _final_message(content: str = "final answer") -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=None)


def _runner(
    responses: list[tuple[Any, int, int]], bus: _FakeBus | None = None,
) -> tuple[AgentRunner, _FakeBus]:
    bus = bus or _FakeBus()
    config = AgentConfig(name="a", role="assistant", capabilities=["noop"])
    parent = _FakeParent(_FakeStreamer(responses))
    return AgentRunner(config, parent, bus=bus), bus


class TestPushStateEvent:
    async def test_event_shape(self) -> None:
        bus = NotificationBus()
        received: list[dict[str, Any]] = []

        async def reader() -> None:
            async for ev in bus.events():
                received.append(ev)
                if ev["type"] == "state":
                    return

        task = asyncio.create_task(reader())
        await asyncio.sleep(0)
        await bus.push_state("EXECUTING", "agent_x", iteration=3)
        await asyncio.wait_for(task, 1)

        ev = received[0]
        assert ev["type"] == "state"
        assert ev["phase"] == "EXECUTING"
        assert ev["agent_id"] == "agent_x"
        assert ev["iteration"] == 3
        assert "timestamp" in ev
        assert ev["seq"] >= 1

    async def test_terminal_phases_omit_iteration(self) -> None:
        bus = NotificationBus()
        received: list[dict[str, Any]] = []

        async def reader() -> None:
            async for ev in bus.events():
                received.append(ev)
                if ev["type"] == "state":
                    return

        task = asyncio.create_task(reader())
        await asyncio.sleep(0)
        await bus.push_state("DONE", "agent_x")
        await asyncio.wait_for(task, 1)
        assert received[0]["iteration"] is None


class TestAgentStatePhases:
    def test_phase_defaults(self) -> None:
        now = datetime.now(UTC)
        config = AgentConfig(name="n", role="r")
        state = AgentState(
            agent_id="a", config=config, status="idle", created_at=now, last_active=now,
        )
        assert state.phase == "IDLE"
        assert state.phase_transitions == []

    def test_phase_transitions_recorded_and_serializable(self) -> None:
        now = datetime.now(UTC)
        config = AgentConfig(name="n", role="r")
        state = AgentState(
            agent_id="a", config=config, status="running", created_at=now, last_active=now,
        )
        state.phase_transitions.append(
            PhaseTransition(phase="DELEGATING", timestamp=now, iteration=2),
        )
        assert state.phase_transitions[0].phase == "DELEGATING"
        assert state.phase_transitions[0].iteration == 2
        dumped = state.model_dump()
        assert dumped["phase"] == "IDLE"
        assert dumped["phase_transitions"][0]["phase"] == "DELEGATING"


class TestRunnerLifecycle:
    async def test_emits_full_lifecycle(self) -> None:
        runner, bus = _runner([(_tool_message(), 10, 5), (_final_message("ok"), 5, 5)])
        await runner.run("task")

        phases = [s["phase"] for s in bus.states]
        assert phases == ["THINKING", "EXECUTING", "REPORTING", "DONE"]
        assert all(s["agent_id"] == runner.agent_id for s in bus.states)
        assert bus.states[0]["iteration"] == 1
        assert bus.states[1]["iteration"] == 1
        assert bus.states[2]["iteration"] is None
        assert bus.states[3]["iteration"] is None
        assert runner.state.phase_transitions[-1].phase == "DONE"

    async def test_delegate_tool_emits_delegating(self) -> None:
        runner, bus = _runner([(_tool_message("delegate_task"), 10, 5), (_final_message("done"), 5, 5)])
        await runner.run("task")

        phases = [s["phase"] for s in bus.states]
        assert phases == ["THINKING", "DELEGATING", "REPORTING", "DONE"]
        assert "EXECUTING" not in phases

    async def test_change_detection_suppresses_duplicate_emits(self) -> None:
        runner, bus = _runner([
            (_tool_message(), 10, 5),
            (_tool_message(), 10, 5),
            (_final_message("ok"), 5, 5),
        ])
        await runner.run("task")

        phases = [s["phase"] for s in bus.states]
        assert phases == ["THINKING", "EXECUTING", "REPORTING", "DONE"]
        assert phases.count("EXECUTING") == 1

    async def test_parallel_agents_scope_events_per_agent(self) -> None:
        bus1, bus2 = _FakeBus(), _FakeBus()
        r1, _ = _runner([(_tool_message(), 10, 5), (_final_message("a"), 5, 5)], bus1)
        r2, _ = _runner([(_final_message("b"), 5, 5)], bus2)

        await asyncio.gather(r1.run("t1"), r2.run("t2"))

        assert {s["agent_id"] for s in bus1.states} == {r1.agent_id}
        assert {s["agent_id"] for s in bus2.states} == {r2.agent_id}
        assert [s["phase"] for s in bus1.states] == ["THINKING", "EXECUTING", "REPORTING", "DONE"]
        assert [s["phase"] for s in bus2.states] == ["THINKING", "REPORTING", "DONE"]


class TestChatOrchestratorLifecycle:
    async def test_send_emits_lifecycle(self) -> None:
        bus = _FakeBus()
        chat = _make_chat(messages=[_tool_message("delegate_task"), _answer_message("done")])
        chat._active_bus = bus

        result = await chat.send("orchestrate", notification_bus=bus)

        assert result == "done"
        phases = [s["phase"] for s in bus.states]
        assert phases == ["THINKING", "DELEGATING", "REPORTING", "DONE"]
        assert all(s["agent_id"] == chat.session_id for s in bus.states)

    async def test_send_executing_for_regular_tools(self) -> None:
        bus = _FakeBus()
        chat = _make_chat(messages=[_tool_message("get_weather"), _answer_message("done")])
        chat._active_bus = bus

        await chat.send("hello", notification_bus=bus)

        phases = [s["phase"] for s in bus.states]
        assert phases == ["THINKING", "EXECUTING", "REPORTING", "DONE"]

    async def test_no_bus_emits_nothing(self) -> None:
        chat = _make_chat(messages=[_answer_message("ok")])
        await chat.send("hello")
        # No _active_bus -> no state events raised
        assert chat._active_bus is None


# ---------------------------------------------------------------------------
# Minimal CliChat stand-in (mirrors tests/test_chat_pipeline.py)
# ---------------------------------------------------------------------------


class _FakeHistory:
    def load_session(self, session_id: str) -> list[dict[str, Any]]:
        return []

    async def async_save_message(self, session_id: str, role: str, content: str) -> None:
        pass


class _FakeContext:
    def trim(self, messages: list[dict[str, Any]], tools_tokens: int = 0) -> list[dict[str, Any]]:
        return messages

    async def auto_index(self, text: str, namespace: str = "messages") -> None:
        pass


class _FakeUsage:
    async def async_record(self, model: str, input_tokens: int, output_tokens: int, session_id: str = "default") -> None:
        pass


class _FakeDocInjector:
    async def resolve(self, text: str) -> str:
        return text


class _FakeRag:
    async def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.25) -> list[dict[str, Any]]:
        return []

    def format_context(self, results: list[dict[str, Any]]) -> str:
        return ""


class _FakeStreamerChat:
    def __init__(self, messages: list[Any]) -> None:
        self._messages = list(messages)

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        message = self._messages.pop(0)
        content = getattr(message, "content", "") or ""
        return message, len(json.dumps([m.get("content", "") for m in messages])), len(content)


class _FakeToolRunnerChat:
    async def execute_tool_calls(self, tool_calls: list[Any], on_tool_event: Any = None, on_approval: Any = None) -> list[dict[str, Any]]:
        return [{"role": "tool", "tool_call_id": "call_1", "content": "result"}]


def _answer_message(content: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=None)


def _make_chat(*, messages: list[Any] | None = None) -> CliChat:
    chat = object.__new__(CliChat)
    chat.claude = SimpleNamespace(model="test-model")
    chat.messages = []
    chat.session_id = "test-session"
    chat.history = _FakeHistory()
    chat.usage = _FakeUsage()
    chat.context = _FakeContext()
    chat.rag = _FakeRag()
    chat.doc_injector = _FakeDocInjector()
    chat.streamer = _FakeStreamerChat(messages or [_answer_message()])
    chat.tool_runner = _FakeToolRunnerChat()
    chat.verifier = None
    chat.moderation = None
    chat.response_format = None
    chat._correction_attempts = 0
    chat.MAX_CORRECTION_ATTEMPTS = 2
    chat._max_tool_iterations = 10
    chat._openai_tools = []
    chat._auto_index_task = None
    chat._active_bus = None
    return chat
