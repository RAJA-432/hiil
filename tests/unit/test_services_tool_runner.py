from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import FakeTool, FakeToolCall

from mcp_cli.services.tool_runner import ToolRunner, _extract_text, _mcp_tool_to_openai


def test_mcp_tool_to_openai():
    tool = FakeTool()
    result = _mcp_tool_to_openai(tool)
    assert result["type"] == "function"
    assert result["function"]["name"] == "test_tool"


def test_extract_text():
    class FakeBlock:
        def __init__(self, text):
            self.text = text
    result = MagicMock(content=[FakeBlock("hello"), FakeBlock("world")])
    assert _extract_text(result) == "hello\nworld"


def test_extract_text_none():
    assert _extract_text(None) == ""


def test_extract_text_empty_content():
    assert _extract_text(MagicMock(content=[])) == ""


@pytest.mark.asyncio
async def test_call_tool_unknown():
    runner = ToolRunner({})
    result = await runner.call_tool("unknown", {})
    assert "Unknown" in result


@pytest.mark.asyncio
async def test_call_tool_success():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="hello world")]))
    runner = ToolRunner({"greet": {"client": client}})
    result = await runner.call_tool("greet", {"name": "test"})
    assert result == "hello world"


@pytest.mark.asyncio
async def test_call_tool_timeout():
    client = AsyncMock()
    client.call_tool = AsyncMock(side_effect=TimeoutError())
    runner = ToolRunner({"slow": {"client": client}}, tool_timeout=0.1)
    result = await runner.call_tool("slow", {})
    assert "timeout" in result


@pytest.mark.asyncio
async def test_call_tool_error():
    client = AsyncMock()
    client.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
    runner = ToolRunner({"fail": {"client": client}})
    result = await runner.call_tool("fail", {})
    assert "Tool error" in result


@pytest.mark.asyncio
async def test_execute_tool_calls_basic():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="done")]))
    runner = ToolRunner({"my_tool": {"client": client}})
    calls = [FakeToolCall()]
    results = await runner.execute_tool_calls(calls)
    assert len(results) == 1
    assert results[0]["role"] == "tool"
    assert "done" in results[0]["content"]


@pytest.mark.asyncio
async def test_execute_tool_calls_with_event():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="result")]))
    runner = ToolRunner({"my_tool": {"client": client}})
    events = []
    calls = [FakeToolCall()]
    results = await runner.execute_tool_calls(calls, on_tool_event=events.append)
    assert len(events) == 2
    assert events[0].name == "my_tool"
    assert events[0].result is None
    assert events[1].result == "result"


@pytest.mark.asyncio
async def test_execute_tool_calls_approval_denied():
    client = AsyncMock()
    runner = ToolRunner({"write_file": {"client": client}})
    calls = [FakeToolCall(name="write_file")]
    approved = []
    async def on_approval(name, args):
        approved.append((name, args))
        return False
    results = await runner.execute_tool_calls(calls, on_approval=on_approval)
    assert len(results) == 1
    assert "denied" in results[0]["content"]
    assert len(approved) == 1


@pytest.mark.asyncio
async def test_execute_tool_calls_approval_allowed():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="written")]))
    runner = ToolRunner({"write_file": {"client": client}})
    calls = [FakeToolCall(name="write_file")]
    async def on_approval(name, args):
        return True
    results = await runner.execute_tool_calls(calls, on_approval=on_approval)
    assert len(results) == 1
    assert "written" in results[0]["content"]


@pytest.mark.asyncio
async def test_execute_tool_calls_non_sensitive_skips_approval():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="data")]))
    runner = ToolRunner({"read_file": {"client": client}})
    calls = [FakeToolCall(name="read_file")]
    called = []
    async def on_approval(name, args):
        called.append((name, args))
        return True
    results = await runner.execute_tool_calls(calls, on_approval=on_approval)
    assert not called


@pytest.mark.asyncio
async def test_execute_tool_calls_json_decode_error():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="ok")]))
    runner = ToolRunner({"my_tool": {"client": client}})
    bad_call = FakeToolCall(args="not-json")
    results = await runner.execute_tool_calls([bad_call])
    assert len(results) == 1
