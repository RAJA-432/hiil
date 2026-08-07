from __future__ import annotations

from types import SimpleNamespace

import mcp_cli.services.builtin_tools as builtin_module
from mcp_cli.services.builtin_tools import (
    BUILTIN_TOOL_SCHEMAS,
    BuiltinToolClient,
    BuiltinTools,
)
from mcp_cli.services.tool_runner import _extract_text


class _FakeRunner:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.config: SimpleNamespace | None = None
        self.run_input: str | None = None

    async def run(self, task: str) -> SimpleNamespace:
        self.run_input = task
        return SimpleNamespace(status="completed", output=f"result for {task}")


class _FakeChat:
    def __init__(self):
        self.agents: dict[str, _FakeRunner] = {}
        self.spawned: list[_FakeRunner] = []
        self.parallel_items: list | None = None

    def spawn_agent(self, config) -> _FakeRunner:
        runner = _FakeRunner(f"agent_{len(self.spawned)}")
        runner.config = config
        self.spawned.append(runner)
        self.agents[runner.agent_id] = runner
        return runner

    async def parallel_spawn(self, items: list) -> list[tuple[str, SimpleNamespace]]:
        self.parallel_items = items
        return [
            (f"agent_{i}", SimpleNamespace(status="completed", output=f"parallel result for {config.name}"))
            for i, (config, _task) in enumerate(items)
        ]


async def _delegate(chat: _FakeChat, args: dict) -> str:
    return await BuiltinToolClient(chat).call_tool("delegate_task", args)


async def _delegate_parallel(chat: _FakeChat, args: dict) -> str:
    return await BuiltinToolClient(chat).call_tool("delegate_parallel", args)


class TestSchemas:
    def test_schemas_register_both_tools(self) -> None:
        assert set(BUILTIN_TOOL_SCHEMAS) == {"delegate_task", "delegate_parallel"}

    def test_register_populates_tools_by_name(self) -> None:
        chat = _FakeChat()
        registry = BuiltinTools(chat)
        tools_by_name: dict = {}
        registry.register(tools_by_name)
        assert set(tools_by_name) == {"delegate_task", "delegate_parallel"}
        for name in tools_by_name:
            assert tools_by_name[name]["openai"]["function"]["name"] == name
            assert callable(tools_by_name[name]["client"].call_tool)


class TestDelegateTask:
    async def test_unknown_agent_falls_back_to_general_purpose(self) -> None:
        chat = _FakeChat()
        result = await _delegate(chat, {"agent": "nope", "task": "do it"})
        assert chat.spawned[0].config.name == "general-purpose"
        assert "delegated to general-purpose" in result

    async def test_requires_task(self) -> None:
        result = await _delegate(_FakeChat(), {"agent": "chinook-analyst"})
        assert "requires a non-empty 'task'" in result

    async def test_registry_agent_is_spawned_and_run(self) -> None:
        chat = _FakeChat()
        result = await _delegate(chat, {"agent": "chinook-analyst", "task": "analyze sales"})
        assert chat.spawned[0].config.name == "chinook-analyst"
        assert chat.spawned[0].run_input == "analyze sales"
        assert "delegated to chinook-analyst" in result
        assert "result for analyze sales" in result

    async def test_dynamic_role_config(self) -> None:
        chat = _FakeChat()
        result = await _delegate(
            chat, {"role": "SQL Expert", "capabilities": ["sqlite"], "task": "query"}
        )
        config = chat.spawned[0].config
        assert config.role == "SQL Expert"
        assert config.capabilities == ["sqlite"]
        assert config.name == "sql-expert"
        assert "delegated to sql-expert" in result

    async def test_no_agent_falls_back_to_general_purpose(self) -> None:
        result = await _delegate(_FakeChat(), {"task": "do it"})
        assert "delegated to general-purpose" in result

    async def test_truncates_long_output(self) -> None:
        chat = _FakeChat()

        async def run(self, task: str) -> SimpleNamespace:
            return SimpleNamespace(status="completed", output="x" * 9000)

        chat.spawned = []
        original = _FakeRunner.run
        _FakeRunner.run = run
        try:
            result = await _delegate(chat, {"agent": "chinook-analyst", "task": "t"})
        finally:
            _FakeRunner.run = original
        assert "[truncated]" in result
        assert len(result) < 5000


class TestDelegateParallel:
    async def test_requires_delegations(self) -> None:
        result = await _delegate_parallel(_FakeChat(), {})
        assert "requires a non-empty 'delegations' list" in result

    async def test_requires_task_per_delegation(self) -> None:
        chat = _FakeChat()
        result = await _delegate_parallel(
            chat, {"delegations": [{"agent": "chinook-analyst"}]}
        )
        assert "Each delegation requires a non-empty 'task'" in result

    async def test_unknown_agent_in_batch_falls_back_to_general_purpose(self) -> None:
        chat = _FakeChat()
        result = await _delegate_parallel(
            chat,
            {"delegations": [
                {"agent": "chinook-analyst", "task": "a"},
                {"agent": "nope", "task": "b"},
            ]},
        )
        assert "delegated to general-purpose" in result
        assert [c.name for c, _t in (chat.parallel_items or [])] == ["chinook-analyst", "general-purpose"]

    async def test_runs_all_delegations(self) -> None:
        chat = _FakeChat()
        result = await _delegate_parallel(
            chat,
            {"delegations": [
                {"agent": "chinook-analyst", "task": "a"},
                {"agent": "genre-researcher", "task": "b"},
            ]},
        )
        assert [c.name for c, _t in chat.parallel_items] == ["chinook-analyst", "genre-researcher"]
        assert "delegated to chinook-analyst" in result
        assert "delegated to genre-researcher" in result
        assert "parallel result for" in result


class TestGuards:
    async def test_depth_limit_blocks_recursion(self) -> None:
        chat = _FakeChat()
        client = BuiltinToolClient(chat)
        ctx = builtin_module._delegation_depth
        token = ctx.set(builtin_module._MAX_DELEGATION_DEPTH)
        try:
            result = await client.call_tool(
                "delegate_task", {"agent": "chinook-analyst", "task": "x"}
            )
        finally:
            ctx.reset(token)
        assert "delegation depth exceeded" in result
        assert chat.spawned == []

    async def test_extract_text_passes_strings_through(self) -> None:
        assert _extract_text("hello") == "hello"


class TestRouterFiltering:
    async def test_hidden_by_default_for_subagents(self) -> None:
        from mcp_cli.services.tool_router import ToolRouter

        client = BuiltinToolClient(_FakeChat())
        tools_by_name = {
            "delegate_task": {
                "client": client,
                "openai": BUILTIN_TOOL_SCHEMAS["delegate_task"],
            }
        }
        router = ToolRouter(tools_by_name=tools_by_name, clients={}, capabilities=["read"])
        assert "delegate_task" not in router.tool_names

    async def test_allowed_with_builtin_capability(self) -> None:
        from mcp_cli.services.tool_router import ToolRouter

        chat = _FakeChat()
        client = BuiltinToolClient(chat)
        tools_by_name = {
            "delegate_task": {
                "client": client,
                "openai": BUILTIN_TOOL_SCHEMAS["delegate_task"],
            }
        }
        router = ToolRouter(
            tools_by_name=tools_by_name, clients={"builtin": client}, capabilities=["builtin"]
        )
        assert "delegate_task" in router.tool_names
