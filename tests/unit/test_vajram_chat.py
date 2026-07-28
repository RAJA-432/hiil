from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from mcp_cli.services.notification_bus import NotificationBus
from vajra_gate.chat import _init_chat, _merge_events, _require_chat, _stream_chat, lekh_record


@pytest.fixture
def mock_chat():
    chat = AsyncMock()
    chat.send = AsyncMock()
    return chat


@pytest.fixture
def mock_state(monkeypatch):
    import vajra_gate.state as _state
    _state._chat = None
    _state._chat_stack = None
    yield _state


@pytest.mark.asyncio
async def test_init_chat_returns_cached(mock_state):
    fake_chat = MagicMock()
    mock_state._chat = fake_chat
    result = await _init_chat()
    assert result is fake_chat


@pytest.mark.asyncio
async def test_init_chat_creates_new(mock_state):
    with patch("mcp_cli.services.factory.create_chat", new_callable=AsyncMock) as mock_create:
        fake_chat = MagicMock()
        mock_create.return_value = fake_chat
        result = await _init_chat()
        assert result is fake_chat
        assert mock_state._chat is fake_chat
        mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_require_chat_returns_chat(mock_state):
    fake_chat = MagicMock()
    mock_state._chat = fake_chat
    request = MagicMock()
    result = await _require_chat(request)
    assert result is fake_chat


@pytest.mark.asyncio
async def test_require_chat_raises_on_failure(mock_state):
    with patch("mcp_cli.services.factory.create_chat", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = RuntimeError("boom")
        request = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await _require_chat(request)
        assert exc_info.value.status_code == 500
        assert "Chat init failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_chat_returns_cached(mock_state):
    chat1 = MagicMock()
    chat2 = MagicMock()
    mock_state._chat = chat1
    with patch("mcp_cli.services.factory.create_chat", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = chat2
        result = await _require_chat(MagicMock())
        assert result is chat1
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_stream_chat_yields_json_events():
    chat = AsyncMock()
    bus = NotificationBus()

    async def fake_send(message, on_chunk=None, on_tool_event=None, notification_bus=None):
        on_chunk("Hello")
        notification_bus.push_tool_call_nowait("tool1", {"a": 1}, "running", "processing")
        await notification_bus.push_done()

    chat.send = fake_send

    events = []
    async for event_data in _stream_chat(chat, "test_msg"):
        event = json.loads(event_data)
        events.append(event)

    types = [e["type"] for e in events]
    assert "tokens" in types
    assert "tool_event" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_stream_chat_tool_event_has_expected_fields():
    chat = AsyncMock()

    async def fake_send(message, on_chunk=None, on_tool_event=None, notification_bus=None):
        event = MagicMock(spec=[])
        event.name = "tool1"
        event.args = {"x": 1}
        event.result = "done"
        on_tool_event(event)
        await notification_bus.push_done()

    chat.send = fake_send

    events = []
    async for event_data in _stream_chat(chat, "test"):
        events.append(json.loads(event_data))

    tool_events = [e for e in events if e["type"] == "tool_event"]
    assert len(tool_events) >= 1





@pytest.mark.asyncio
async def test_log_events_without_chat_log():
    bus = NotificationBus()
    async def _run():
        events = []
        async for e in bus.events():
            events.append(e["type"])
        return events
    task = asyncio.create_task(_run())
    await asyncio.sleep(0)
    await bus.push_done()
    result = await asyncio.wait_for(task, timeout=5)
    assert result == ["done"]


@pytest.mark.asyncio
async def test_log_events_with_chat_log(tmp_path):
    """Test that lekh_record properly writes events when VAJRA_GATE_CHAT_LOG is set."""
    log_file = tmp_path / "chat.log"
    bus = NotificationBus()

    # Push a test event and done signal
    async def push_events():
        await asyncio.sleep(0)  # Let consumer start
        await bus.push_log("info", "test log entry")
        await bus.push_done()

    # Start the event pusher task
    pusher = asyncio.create_task(push_events())

    # Patch the log path and run lekh_record
    with patch("vajra_gate.config.VAJRA_GATE_CHAT_LOG", str(log_file)):
        await lekh_record(bus)

    await pusher

    # Verify the log file was created and contains the message
    assert log_file.exists(), "Log file should exist after lekh_record completes"
    content = log_file.read_text(encoding="utf-8")
    assert "test log entry" in content, "Log file should contain the test message"


@pytest.mark.asyncio
async def test_log_events_file_write_failure():
    bus = NotificationBus()
    with patch("vajra_gate.config.VAJRA_GATE_CHAT_LOG", "/nonexistent_dir/log.txt"):
        task = asyncio.create_task(lekh_record(bus))
        for _ in range(50):
            await asyncio.sleep(0)
        await bus.push_log("info", "test")
        await bus.push_done()
        try:
            await asyncio.wait_for(task, timeout=5)
        except TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


@pytest.mark.asyncio
async def test_merge_events_yields_from_bus():
    bus = NotificationBus()
    chat = AsyncMock()

    async def fake_send(message, on_chunk=None, on_tool_event=None, notification_bus=None):
        await notification_bus.push_tokens("Hello")
        await notification_bus.push_done()

    chat.send = fake_send

    results = []
    async for event in _merge_events(bus, chat, "hi", lambda c: None, lambda e: None):
        results.append(event)

    types = [e["type"] for e in results]
    assert "tokens" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_merge_events_cancels_tasks_on_generator_exit():
    """Breaking out of the generator should cancel background tasks and not hang."""
    bus = NotificationBus()
    chat = AsyncMock()
    chat.send = AsyncMock(side_effect=lambda msg, **kw: asyncio.sleep(999))

    # Pre-load so the generator yields immediately.
    bus.push_tokens_nowait("dummy")

    gen = _merge_events(bus, chat, "hi", lambda c: None, lambda e: None)

    # Consume one event and break — triggers aclose / GeneratorExit
    collected = []
    async for event in gen:
        collected.append(event)
        break

    assert len(collected) == 1
    assert collected[0]["type"] == "tokens"


@pytest.mark.asyncio
async def test_merge_events_handles_chat_send_failure():
    bus = NotificationBus()
    chat = AsyncMock()
    chat.send.side_effect = RuntimeError("chat crashed")

    results = []
    async for event in _merge_events(bus, chat, "hi", lambda c: None, lambda e: None):
        results.append(event)

    assert any(e["type"] == "done" for e in results)
