from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_cli.services.streamer import Streamer


@pytest.mark.asyncio
async def test_chat_without_on_chunk():
    claude = MagicMock()
    claude.model = "gpt-4o"
    claude.chat = AsyncMock()
    claude.chat.return_value = MagicMock(content="Hello response", tool_calls=None)
    streamer = Streamer(claude)
    msg, inp, out = await streamer.chat([{"role": "user", "content": "hi"}])
    assert msg.content == "Hello response"
    assert isinstance(inp, int) and inp > 0
    assert isinstance(out, int) and out > 0


@pytest.mark.asyncio
async def test_stream_fallback_on_error():
    claude = MagicMock()
    claude.model = "gpt-4o"

    async def failing_stream(*args, **kwargs):
        raise RuntimeError("stream failed")
        yield  # pragma: no cover
    claude.stream_chat = failing_stream
    claude.chat = AsyncMock()
    claude.chat.return_value = MagicMock(content="Fallback response", tool_calls=None)
    streamer = Streamer(claude)
    chunks = []
    msg, inp, out = await streamer.chat([{"role": "user", "content": "hi"}], on_chunk=chunks.append)
    assert msg.content == "Fallback response"


@pytest.mark.asyncio
async def test_stream_with_content():
    claude = MagicMock()
    claude.model = "gpt-4o"

    async def fake_stream(*args, **kwargs):
        yield "content", "Hello"
        yield "content", " world"
        yield "done", "Hello world"

    claude.stream_chat = fake_stream
    streamer = Streamer(claude)
    chunks = []
    msg, inp, out = await streamer.chat([{"role": "user", "content": "hi"}], on_chunk=chunks.append)
    assert "".join(chunks) == "Hello world"
    assert msg.content == "Hello world"


@pytest.mark.asyncio
async def test_stream_with_tool_calls():
    claude = MagicMock()
    claude.model = "gpt-4o"

    async def fake_stream(*args, **kwargs):
        yield "tool_call", {"id": "call_1", "name": "get_weather", "arguments": '{"city":"London"}'}
        yield "done", ""

    claude.stream_chat = fake_stream
    streamer = Streamer(claude)
    chunks = []
    msg, inp, out = await streamer.chat([{"role": "user", "content": "weather"}], on_chunk=chunks.append)
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].function.name == "get_weather"
