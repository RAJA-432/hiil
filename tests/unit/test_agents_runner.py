from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cli.services.agents.interrupts import ActionRequest, ResumeDecision
from mcp_cli.services.agents.models import AgentConfig
from mcp_cli.services.agents.runner import AgentRunner


@pytest.fixture
def config():
    return AgentConfig(name="test_bot", role="helper", max_iterations=5)


@pytest.fixture
def parent_chat():
    chat = MagicMock()
    chat.tools_by_name = {}
    chat.clients = {}
    chat.streamer = MagicMock()
    chat.streamer.chat = AsyncMock()
    chat.streamer.chat.return_value = (MagicMock(content="done", tool_calls=None), 10, 20)
    return chat


@pytest.fixture
def runner(config, parent_chat):
    return AgentRunner(config=config, parent_chat=parent_chat)


class TestConstructor:
    def test_sets_agent_id_and_state(self, runner):
        assert runner.agent_id.startswith("agent_")
        assert runner.state.status == "idle"
        assert runner.state.config.name == "test_bot"

    def test_configures_tool_router(self, runner, config):
        assert runner.tool_router is not None

    def test_no_permission_enforcer_when_no_permissions(self, runner):
        assert runner._perm_enforcer is None

    def test_permission_enforcer_created_when_permissions_given(self):
        from mcp_cli.services.agents.permissions import FilesystemPermission
        cfg = AgentConfig(
            name="secure", role="worker",
            permissions=[FilesystemPermission(operations=["read"], paths=["/*"], mode="allow")],
        )
        chat = MagicMock()
        chat.tools_by_name = {}
        chat.clients = {}
        chat.streamer = MagicMock()
        r = AgentRunner(config=cfg, parent_chat=chat)
        assert r._perm_enforcer is not None

    def test_properties(self, runner):
        assert runner.messages == []
        assert runner.virtual_files == {}


class TestRun:
    @pytest.mark.asyncio
    async def test_run_completes_successfully(self, runner, parent_chat):
        result = await runner.run("do something")
        assert result.status == "completed"
        assert result.output == "done"
        assert result.tool_calls_made == 0
        assert result.error is None
        assert runner.state.status == "completed"

    @pytest.mark.asyncio
    async def test_run_injects_system_prompt(self, runner):
        await runner.run("hello")
        assert runner.messages[0]["role"] == "system"
        assert "helper" in runner.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_run_uses_custom_system_prompt(self, config, parent_chat):
        config.system_prompt = "You are a custom bot."
        r = AgentRunner(config=config, parent_chat=parent_chat)
        await r.run("hello")
        assert r.messages[0]["content"] == "You are a custom bot."

    @pytest.mark.asyncio
    async def test_run_with_tool_call(self, runner, parent_chat):
        tc = MagicMock()
        tc.function.name = "greet"
        tc.function.arguments = '{"name":"test"}'
        tc.id = "call_1"

        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.side_effect = [
            (MagicMock(content="", tool_calls=[tc]), 10, 20),
            (MagicMock(content="final answer", tool_calls=None), 5, 10),
        ]

        result = await runner.run("do it")
        assert result.output == "final answer"
        assert result.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_run_max_iterations(self, config, parent_chat):
        config.max_iterations = 2
        tc = MagicMock()
        tc.function.name = "loop"
        tc.function.arguments = "{}"
        tc.id = "call_loop"

        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.return_value = (MagicMock(content="", tool_calls=[tc]), 5, 5)

        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("loop forever")
        assert "Max iterations" in result.output
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_human_in_the_loop_interrupt(self, config, parent_chat):
        config.interrupt_on = {"approve_me": True}
        tc = MagicMock()
        tc.function.name = "approve_me"
        tc.function.arguments = '{"cmd":"destroy"}'
        tc.id = "call_1"

        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.return_value = (MagicMock(content="", tool_calls=[tc]), 5, 5)

        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("dangerous task")
        assert result.status == "waiting"
        assert result.pending_interrupt is not None
        assert len(result.pending_interrupt) == 1
        assert result.pending_interrupt[0].name == "approve_me"
        assert r.state.pending_interrupt is not None

    @pytest.mark.asyncio
    async def test_timeout(self, config, parent_chat):
        config.timeout_seconds = 0.01
        parent_chat.streamer.chat = AsyncMock(side_effect=TimeoutError())
        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("slow task")
        assert result.status == "failed"
        assert "timed out" in (result.error or "")

    @pytest.mark.asyncio
    async def test_token_budget_exceeded(self, config, parent_chat):
        config.token_budget = 10
        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.return_value = (MagicMock(content="", tool_calls=None), 100, 0)
        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("spend tokens")
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_stop(self, runner):
        await runner.stop()
        assert runner.state.status == "failed"

    @pytest.mark.asyncio
    async def test_resume_without_pending_raises(self, runner):
        with pytest.raises(RuntimeError, match="No pending interrupt"):
            await runner.resume([ResumeDecision(type="approve")])


class TestResume:
    @pytest.mark.asyncio
    async def test_resume_approve(self, runner, parent_chat):
        runner._state.pending_interrupt = [
            ActionRequest(name="greet", args={"name": "test"}),
        ]
        runner._resume_event.set = MagicMock()
        parent_chat.streamer.chat.return_value = (MagicMock(content="resumed", tool_calls=None), 5, 5)

        result = await runner.resume([ResumeDecision(type="approve")])
        assert result.status == "completed"
        assert "resumed" in result.output

    @pytest.mark.asyncio
    async def test_resume_reject(self, runner, parent_chat):
        runner._state.pending_interrupt = [
            ActionRequest(name="danger", args={"cmd": "rm"}),
        ]
        runner._resume_event.set = MagicMock()
        parent_chat.streamer.chat.return_value = (MagicMock(content="ok", tool_calls=None), 5, 5)

        result = await runner.resume([ResumeDecision(type="reject", message="not needed")])
        assert result.status == "completed"
        tool_msg = [m for m in runner.messages if m.get("role") == "tool"]
        assert any("not needed" in m.get("content", "") for m in tool_msg)

    @pytest.mark.asyncio
    async def test_resume_edit(self, runner, parent_chat):
        runner._state.pending_interrupt = [
            ActionRequest(name="write_file", args={"path": "/x.txt", "content": "old"}),
        ]
        runner._resume_event.set = MagicMock()
        parent_chat.streamer.chat.return_value = (MagicMock(content="edited", tool_calls=None), 5, 5)

        result = await runner.resume([
            ResumeDecision(type="edit", edited_action={"name": "write_file", "args": {"path": "/x.txt", "content": "new"}}),
        ])
        assert result.status == "completed"


class TestMemory:
    @pytest.mark.asyncio
    async def test_inject_memory(self, config, parent_chat):
        config.memory_files = ["/notes.md"]
        r = AgentRunner(config=config, parent_chat=parent_chat)
        r._memory = MagicMock()
        r._memory.load_all.return_value = {"/notes.md": "persisted content"}
        r._memory.snapshot_hashes.return_value = {"/notes.md": hash("persisted content")}
        await r._inject_memory()
        assert r._memory_snapshot["/notes.md"] == hash("persisted content")

    @pytest.mark.asyncio
    async def test_virtual_files_property(self, runner):
        runner._virtual_backend._files["/test.txt"] = "hello"
        assert runner.virtual_files == {"/test.txt": "hello"}

    @pytest.mark.asyncio
    async def test_add_route(self, runner):
        runner.add_route("/out/", "/tmp/test_out")
        assert len(runner._virtual_backend._routes) == 1


class TestExecuteToolCalls:
    @pytest.mark.asyncio
    async def test_middleware_intercept(self, config, parent_chat):
        mw = MagicMock()
        mw.handle_tool = AsyncMock(return_value=(True, "intercepted"))
        mw.get_extra_tools.return_value = []
        mw.before_run.side_effect = lambda msgs: msgs
        config.middleware = [mw]

        tc = MagicMock()
        tc.function.name = "custom_tool"
        tc.function.arguments = "{}"
        tc.id = "call_1"

        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.side_effect = [
            (MagicMock(content="", tool_calls=[tc]), 5, 5),
            (MagicMock(content="done", tool_calls=None), 5, 5),
        ]

        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("use middleware")
        assert result.status == "completed"
        # Middleware tool result should be in messages
        tool_msg = [m for m in r.messages if m.get("role") == "tool"]
        assert any("intercepted" in m.get("content", "") for m in tool_msg)

    @pytest.mark.asyncio
    async def test_permission_denied(self, config, parent_chat):
        from mcp_cli.services.agents.permissions import FilesystemPermission
        config.permissions = [FilesystemPermission(operations=["write"], paths=["/*"], mode="deny")]

        tc = MagicMock()
        tc.function.name = "write_file"
        tc.function.arguments = '{"path":"/tmp/x.txt","content":"hi"}'
        tc.id = "call_1"

        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.side_effect = [
            (MagicMock(content="", tool_calls=[tc]), 5, 5),
            (MagicMock(content="done", tool_calls=None), 5, 5),
        ]

        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("write")
        assert result.status == "completed"
        tool_msg = [m for m in r.messages if m.get("role") == "tool"]
        assert any("denied" in m.get("content", "") for m in tool_msg)

    @pytest.mark.asyncio
    async def test_virtual_backend_intercept(self, config, parent_chat):
        tc = MagicMock()
        tc.function.name = "write_file"
        tc.function.arguments = '{"path":"/mem/test.txt","content":"hello"}'
        tc.id = "call_1"

        parent_chat.streamer.chat = AsyncMock()
        parent_chat.streamer.chat.side_effect = [
            (MagicMock(content="", tool_calls=[tc]), 5, 5),
            (MagicMock(content="done", tool_calls=None), 5, 5),
        ]

        r = AgentRunner(config=config, parent_chat=parent_chat)
        result = await r.run("write virtual")
        assert result.status == "completed"
        assert r._virtual_backend.get_file("/mem/test.txt") == "hello"
