from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import mcp_cli.services.agents.runner as runner_module
from mcp_cli.services.agents.interrupts import ResumeDecision
from mcp_cli.services.agents.memory import AgentMemoryStore
from mcp_cli.services.agents.models import AgentConfig
from mcp_cli.services.agents.runner import AgentRunner


class _FakeClient:
    async def call_tool(self, name: str, args: dict) -> str:
        return f"result from {name}"


class FakeStreamer:
    def __init__(self, responses: list[tuple[Any, int, int]]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        self.call_count += 1
        message, input_tokens, output_tokens = self._responses.pop(0)
        return message, input_tokens, output_tokens


class FakeParentChat:
    def __init__(self, streamer: FakeStreamer) -> None:
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


def _interrupt_batch_message() -> SimpleNamespace:
    return SimpleNamespace(
        content="",
        tool_calls=[
            SimpleNamespace(id="call_noop", function=SimpleNamespace(name="noop", arguments="{}")),
            SimpleNamespace(
                id="call_send",
                function=SimpleNamespace(
                    name="send_draft",
                    arguments='{"to": "a@b.c", "subject": "hi", "body": "body"}',
                ),
            ),
        ],
    )


def _final_message(content: str = "final answer") -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=None)


async def _wait_for(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met before timeout")
        await asyncio.sleep(0.01)


def _runner(responses: list[tuple[Any, int, int]], **overrides: Any) -> AgentRunner:
    config = AgentConfig(
        name="a",
        role="assistant",
        capabilities=["noop"],
        interrupt_on={"send_draft": True},
        **overrides,
    )
    return AgentRunner(config, FakeParentChat(FakeStreamer(responses)))


class TestInterruptResume:
    async def test_interrupt_pauses_then_resume_completes(self) -> None:
        runner = _runner([(_interrupt_batch_message(), 100, 10), (_final_message(), 10, 5)])

        run_task = asyncio.create_task(runner.run("do it"))
        await _wait_for(lambda: runner.state.status == "waiting")

        assert runner.state.pending_interrupt is not None
        assert runner.state.pending_interrupt[0].name == "send_draft"

        result = await runner.resume([ResumeDecision(type="approve")])
        assert result.status == "completed"
        assert result.output == "final answer"
        await run_task

        # Full batch tool results recorded exactly once (partial noop + approved gated tool).
        tool_msgs = [m for m in runner.messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 2

    async def test_resume_records_gated_batch_and_completes(self) -> None:
        runner = _runner([(_interrupt_batch_message(), 100, 10), (_final_message("done"), 10, 5)])

        run_task = asyncio.create_task(runner.run("do it"))
        await _wait_for(lambda: runner.state.status == "waiting")
        assert runner.state.pending_interrupt is not None
        assert runner.state.pending_interrupt[0].name == "send_draft"

        result = await runner.resume([ResumeDecision(type="approve")])
        assert result.status == "completed"
        assert result.output == "done"
        await run_task

        # Paused mid-batch on send_draft: the earlier noop result is recorded too.
        tool_msgs = [m for m in runner.messages if m.get("role") == "tool"]
        assert [m["tool_call_id"] for m in tool_msgs] == ["call_noop", "call_send"]
        assert "noop" in tool_msgs[0]["content"]
        assert "send_draft" in tool_msgs[1]["content"]
        assert runner.state.phase_transitions[-1].phase == "DONE"

    async def test_stop_unblocks_waiting_agent_and_records_partial_results(self) -> None:
        runner = _runner([(_interrupt_batch_message(), 100, 10), (_final_message(), 10, 5)])

        run_task = asyncio.create_task(runner.run("do it"))
        await _wait_for(lambda: runner.state.status == "waiting")

        await runner.stop()
        result = await run_task

        assert result.status == "failed"
        # Partial progress (the noop call) recorded before the abort.
        tool_msgs = [m for m in runner.messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "noop" in tool_msgs[0]["content"]

    async def test_resume_without_pending_interrupt_raises(self) -> None:
        runner = _runner([])
        try:
            await runner.resume([ResumeDecision(type="approve")])
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "No pending interrupt" in str(exc)

    async def test_reject_decision_skips_tool_execution(self) -> None:
        runner = _runner([(_interrupt_batch_message(), 100, 10), (_final_message(), 10, 5)])

        run_task = asyncio.create_task(runner.run("do it"))
        await _wait_for(lambda: runner.state.status == "waiting")

        result = await runner.resume([ResumeDecision(type="reject", message="not now")])
        assert result.status == "completed"
        await run_task

        rejected = [m for m in runner.messages if m.get("role") == "tool" and "rejected" in m.get("content", "")]
        assert len(rejected) == 1


class TestRunnerMemoryPersistence:
    async def test_persist_memory_writes_block_after_marker(self, tmp_path, monkeypatch) -> None:
        store = AgentMemoryStore(tmp_path)
        monkeypatch.setattr(runner_module, "_get_memory_store", lambda: store)
        final = _final_message("Done.\n## Persistent Memory\n# Memory: notes.md\nv2 updated content")
        runner = _runner([(final, 10, 5)], memory_files=["notes.md"])
        store.write(runner.agent_id, "notes.md", "v1 original content")

        result = await runner.run("do it")

        assert result.status == "completed"
        assert store.read(runner.agent_id, "notes.md") == "v2 updated content"

    async def test_persist_memory_skips_when_unchanged(self, tmp_path, monkeypatch) -> None:
        store = AgentMemoryStore(tmp_path)
        monkeypatch.setattr(runner_module, "_get_memory_store", lambda: store)
        runner = _runner([(_final_message(), 10, 5)], memory_files=["notes.md"])
        store.write(runner.agent_id, "notes.md", "v1")

        await runner.run("do it")

        assert store.read(runner.agent_id, "notes.md") == "v1"

    async def test_persist_memory_writes_when_no_prior_file(self, tmp_path, monkeypatch) -> None:
        store = AgentMemoryStore(tmp_path)
        monkeypatch.setattr(runner_module, "_get_memory_store", lambda: store)
        final = _final_message("## Persistent Memory\n# Memory: notes.md\nfresh content")
        runner = _runner([(final, 10, 5)], memory_files=["notes.md"])

        await runner.run("do it")

        assert store.read(runner.agent_id, "notes.md") == "fresh content"

    async def test_persist_memory_writes_to_dot_agent_memory(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr(runner_module, "_MEMORY_STORE", None)
        final = _final_message("## Persistent Memory\n# Memory: notes.md\npersisted content")
        runner = _runner([(final, 10, 5)], memory_files=["notes.md"])

        result = await runner.run("do it")

        assert result.status == "completed"
        store = runner_module._get_memory_store()
        assert store.read(runner.agent_id, "notes.md") == "persisted content"
        expected = (tmp_path / ".agent_memory" / "agent" / runner.agent_id / "notes.md").resolve()
        assert expected.exists()
