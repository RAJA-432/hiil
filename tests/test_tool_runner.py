from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcp_cli.services.roots import RootsManager
from mcp_cli.services.tool_runner import ToolRunner


class _FakeBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeCallResult:
    def __init__(self, text: str = "tool output"):
        self.content = [_FakeBlock(text)]


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, args: dict[str, Any]) -> _FakeCallResult:
        self.calls.append((name, args))
        return _FakeCallResult(f"result from {name}")


class _FakeCall:
    def __init__(self, name: str, args: str = "{}", call_id: str = "call_1"):
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=args)


def _runner(*names: str) -> tuple[ToolRunner, _FakeClient]:
    client = _FakeClient()
    runner = ToolRunner(
        tools_by_name={name: {"client": client} for name in names},
        roots_manager=RootsManager(["."]),
    )
    return runner, client


async def test_sensitive_tool_invokes_approval_before_execution():
    runner, client = _runner("write_file")
    approvals: list[tuple[str, dict[str, Any]]] = []

    async def on_approval(name: str, args: dict[str, Any]) -> bool:
        approvals.append((name, args))
        return True

    results = await runner.execute_tool_calls(
        [_FakeCall("write_file", '{"path": "notes.txt"}')],
        on_approval=on_approval,
    )
    assert approvals == [("write_file", {"path": "notes.txt"})]
    assert client.calls == [("write_file", {"path": "notes.txt"})]
    assert "result from write_file" in results[0]["content"]


async def test_benign_tool_skips_approval():
    runner, client = _runner("get_weather")
    called = False

    async def on_approval(name: str, args: dict[str, Any]) -> bool:
        nonlocal called
        called = True
        return True

    results = await runner.execute_tool_calls(
        [_FakeCall("get_weather", '{"city": "Tokyo"}')],
        on_approval=on_approval,
    )
    assert called is False
    assert client.calls == [("get_weather", {"city": "Tokyo"})]
    assert "result from get_weather" in results[0]["content"]


async def test_rejected_sensitive_tool_skips_execution():
    runner, client = _runner("delete_file")

    async def on_approval(name: str, args: dict[str, Any]) -> bool:
        return False

    results = await runner.execute_tool_calls(
        [_FakeCall("delete_file", '{"path": "notes.txt"}')],
        on_approval=on_approval,
    )
    assert client.calls == []
    content = results[0]["content"]
    assert "[denied]" in content
    assert "delete_file" in content
    assert "rejected by user" in content


async def test_no_on_approval_executes_without_gate():
    runner, client = _runner("write_file")
    results = await runner.execute_tool_calls(
        [_FakeCall("write_file", '{"path": "notes.txt"}')],
    )
    assert client.calls == [("write_file", {"path": "notes.txt"})]
    assert "result from write_file" in results[0]["content"]
