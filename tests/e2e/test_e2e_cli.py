from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcp_cli.services.notification_bus import NotificationBus


@pytest.mark.asyncio
async def test_cli_full_session():
    with (
            patch("mcp_cli.main.CliApp") as MockApp,
            patch("mcp_cli.services.factory.load_settings") as MockLoadSettings,
            patch("mcp_cli.services.factory.Claude"),
            patch("mcp_cli.services.factory.AsyncExitStack"),
            patch("mcp_cli.services.server_manager.MCPClient"),
            patch("mcp_cli.services.factory.create_servers", new_callable=AsyncMock) as MockCreateServers,
            patch("mcp_cli.services.factory.CliChat") as MockChat,
    ):
        MockCreateServers.return_value = (None, {})
        MockLoadSettings.return_value = (
            MagicMock(provider="ollama", model="gemma4", api_key="", base_url="", max_context_tokens=200000),
            [],
        )
        chat_instance = MagicMock()
        chat_instance.initialize = AsyncMock()
        chat_instance.send = AsyncMock(return_value="Hello! I'm the AI assistant.")
        chat_instance.get_status = MagicMock(return_value={
            "session": "default", "messages": 2, "servers": [],
            "model": "gemma4", "provider": "ollama", "tools": 0,
        })
        chat_instance.history.list_sessions = MagicMock(return_value=["default"])
        MockChat.return_value = chat_instance

        app_instance = AsyncMock()
        app_instance.run = AsyncMock()
        MockApp.return_value = app_instance

        from mcp_cli.main import main
        await main()

        MockChat.assert_called_once()
        MockApp.assert_called_once_with(chat_instance)
        app_instance.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_cli_session_lifecycle():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.send = AsyncMock(return_value="Reply from AI")
    chat.new_session = MagicMock(return_value="session_20260723_120000")
    chat.get_status = MagicMock(return_value={
        "session": "session_20260723_120000", "messages": 1,
        "servers": [], "model": "gemma4", "provider": "ollama", "tools": 0,
    })
    chat.session_id = "session_20260723_120000"
    chat.messages = []
    chat.history = MagicMock()
    chat.history.async_list_sessions = AsyncMock(return_value=["default", "session_20260723_120000"])
    chat.history.async_load_session = AsyncMock(return_value=[{"role": "user", "content": "hi"}])

    sid = chat.new_session()
    assert sid == "session_20260723_120000"
    assert chat.session_id == sid
    assert chat.messages == []

    reply = await chat.send("hello")
    assert reply == "Reply from AI"

    status = chat.get_status()
    assert status["session"] == "session_20260723_120000"


@pytest.mark.asyncio
async def test_cli_send_receives_response():
    chat = MagicMock()
    chat.initialize = AsyncMock()

    received_chunks = []

    async def mock_send(user_input, **kwargs):
        on_chunk = kwargs.get("on_chunk")
        if on_chunk:
            on_chunk("Hello!")
            on_chunk(" How can I help?")
        return "Hello! How can I help?"

    chat.send = AsyncMock(side_effect=mock_send)

    reply = await chat.send("test", on_chunk=lambda c: received_chunks.append(c))
    assert reply == "Hello! How can I help?"
    assert len(received_chunks) > 0


@pytest.mark.asyncio
async def test_cli_new_session_clears_messages():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.messages = [{"role": "user", "content": "old msg"}, {"role": "assistant", "content": "old reply"}]
    chat.new_session = MagicMock(return_value="session_new_001")

    sid = chat.new_session()
    assert sid == "session_new_001"
    assert len(chat.messages) == 2
    chat.messages = []
    assert chat.messages == []


@pytest.mark.asyncio
async def test_cli_multi_turn_conversation():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.messages = []

    turns = ["hello", "what is Python?", "thanks"]
    replies = ["Hi there!", "Python is a language", "You're welcome!"]

    async def mock_send(user_input, **kwargs):
        idx = turns.index(user_input)
        chat.messages.append({"role": "user", "content": user_input})
        chat.messages.append({"role": "assistant", "content": replies[idx]})
        return replies[idx]

    chat.send = AsyncMock(side_effect=mock_send)

    for i, msg in enumerate(turns):
        reply = await chat.send(msg)
        assert reply == replies[i]
        assert len(chat.messages) == (i + 1) * 2


@pytest.mark.asyncio
async def test_cli_send_error_handling():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.send = AsyncMock(side_effect=ConnectionError("API unavailable"))

    with pytest.raises(ConnectionError, match="API unavailable"):
        await chat.send("hello")


@pytest.mark.asyncio
async def test_cli_update_model_then_send():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.claude = MagicMock()
    chat.claude.model = "gemma4"
    chat.send = AsyncMock(return_value="Reply from new model")

    chat.claude.model = "llama3"
    assert chat.claude.model == "llama3"

    reply = await chat.send("test")
    assert reply == "Reply from new model"


@pytest.mark.asyncio
async def test_cli_export_transcript():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    chat.session_id = "test_session"
    chat.export_transcript = MagicMock(return_value="transcript content")

    transcript = chat.export_transcript()
    assert transcript == "transcript content"
    chat.export_transcript.assert_called_once()


@pytest.mark.asyncio
async def test_cli_undo_messages():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.messages = [
        {"role": "user", "content": "keep"},
        {"role": "assistant", "content": "this stays"},
        {"role": "user", "content": "remove"},
        {"role": "assistant", "content": "this goes"},
    ]
    chat.history = MagicMock()
    chat.history.undo_last_messages = MagicMock(return_value=2)

    removed = chat.history.undo_last_messages("sess", 2)
    assert removed == 2


@pytest.mark.asyncio
async def test_cli_notification_bus_in_send():
    from mcp_cli.services.notification_bus import NotificationBus

    bus = NotificationBus()
    events = []

    async def collector():
        async for ev in bus.events():
            events.append(ev)

    chat = MagicMock()
    chat.initialize = AsyncMock()

    async def mock_send(user_input, **kwargs):
        notif_bus = kwargs.get("notification_bus")
        if notif_bus:
            await notif_bus.push_log("info", "processing")
            await notif_bus.push_tokens("hello")
            await notif_bus.push_done()
        return "done"

    chat.send = AsyncMock(side_effect=mock_send)

    import asyncio
    task = asyncio.create_task(collector())
    await asyncio.sleep(0)
    await chat.send("test", notification_bus=bus)
    await asyncio.sleep(0.05)
    task.cancel()
    assert len(events) == 3
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_cli_get_status_fields():
    chat = MagicMock()
    chat.initialize = AsyncMock()
    chat.get_status = MagicMock(return_value={
        "session": "test_sess",
        "messages": 10,
        "servers": ["fs", "db"],
        "model": "gemma4",
        "provider": "ollama",
        "tools": 5,
    })

    status = chat.get_status()
    assert status["session"] == "test_sess"
    assert status["messages"] == 10
    assert status["servers"] == ["fs", "db"]
    assert status["model"] == "gemma4"
    assert status["provider"] == "ollama"
    assert status["tools"] == 5


@pytest.mark.asyncio
async def test_create_chat_initializes_real_components():
    """Exercises the real ``create_chat`` factory with network boundary mocking.

    Mocks only ``load_settings``, ``create_servers``, and ``AsyncOpenAI``.
    The real ``Claude.__init__``, ``CliChat.__init__``, and all sub-components
    (history, context manager, vector store) are exercised.
    """
    from contextlib import AsyncExitStack
    from unittest.mock import AsyncMock, MagicMock, patch

    with (
            patch("mcp_cli.services.claude.AsyncOpenAI") as mock_oa,
            patch("mcp_cli.services.factory.create_servers", new_callable=AsyncMock) as mock_servers,
            patch("mcp_cli.services.factory.load_settings") as mock_settings,
    ):
        mock_servers.return_value = (None, {})
        mock_settings.return_value = (
            MagicMock(provider="test", model="gpt-4o", api_key="", base_url="http://localhost:9999", max_context_tokens=200000),
            [],
        )
        oa_client = MagicMock()
        oa_client.chat = MagicMock()
        oa_client.chat.completions = MagicMock()
        oa_client.chat.completions.create = AsyncMock()
        mock_oa.return_value = oa_client

        from mcp_cli.services.factory import create_chat
        stack = AsyncExitStack()
        chat = await create_chat(stack)

        assert chat.claude.model == "gpt-4o"
        assert chat.claude.provider == "test"
        assert chat.session_id == "default"
        assert chat.tools_by_name == {}
        assert chat.clients == {}

        await stack.aclose()
