from __future__ import annotations

import pytest

from mcp_cli.services.agents.middleware import AgentMiddleware, MiddlewarePipeline


class _AppendMiddleware(AgentMiddleware):
    def __init__(self, suffix: str):
        self._suffix = suffix

    def before_run(self, messages):
        return messages + [{"role": "assistant", "content": self._suffix}]

    def get_extra_tools(self):
        return [{"type": "function", "function": {"name": f"tool_{self._suffix}"}}]

    async def handle_tool(self, name, args):
        if name == self._suffix:
            return (True, f"handled_by_{self._suffix}")
        return (False, None)


@pytest.fixture
def pipeline():
    mw1 = _AppendMiddleware("mw1")
    mw2 = _AppendMiddleware("mw2")
    return MiddlewarePipeline([mw1, mw2])


class TestMiddlewarePipeline:
    def test_before_run_chains_middleware(self, pipeline):
        result = pipeline.before_run([{"role": "user", "content": "hi"}])
        assert len(result) == 3
        assert result[-2]["content"] == "mw1"
        assert result[-1]["content"] == "mw2"

    def test_before_run_empty_pipeline(self):
        pipeline = MiddlewarePipeline([])
        msgs = [{"role": "user", "content": "hello"}]
        assert pipeline.before_run(msgs) is msgs

    def test_get_extra_tools_aggregates(self, pipeline):
        tools = pipeline.get_extra_tools()
        assert len(tools) == 2
        assert tools[0]["function"]["name"] == "tool_mw1"
        assert tools[1]["function"]["name"] == "tool_mw2"

    @pytest.mark.asyncio
    async def test_handle_tool_first_match_wins(self, pipeline):
        handled, result = await pipeline.handle_tool("mw1", {})
        assert handled is True
        assert result == "handled_by_mw1"

    @pytest.mark.asyncio
    async def test_handle_tool_second_middleware(self, pipeline):
        handled, result = await pipeline.handle_tool("mw2", {})
        assert handled is True
        assert result == "handled_by_mw2"

    @pytest.mark.asyncio
    async def test_handle_tool_unhandled(self, pipeline):
        handled, result = await pipeline.handle_tool("unknown", {})
        assert handled is False
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_tool_empty_pipeline(self):
        pipeline = MiddlewarePipeline([])
        handled, result = await pipeline.handle_tool("anything", {})
        assert handled is False
        assert result is None

    def test_middleware_base_returns_defaults(self):
        mw = AgentMiddleware()
        assert mw.before_run([{"role": "user", "content": "x"}]) == [{"role": "user", "content": "x"}]
        assert mw.get_extra_tools() == []

    @pytest.mark.asyncio
    async def test_middleware_base_handle_tool_default(self):
        mw = AgentMiddleware()
        handled, result = await mw.handle_tool("anything", {})
        assert handled is False
        assert result is None
