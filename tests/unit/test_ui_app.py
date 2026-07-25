import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cli.ui.app import CliApp


@pytest.fixture
def chat():
    c = MagicMock()
    c.tools_by_name = {"tool1": {"openai": {"function": {"name": "tool1"}}}}
    c.usage.session_summary.return_value = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150, "cost": 0.003}
    c.usage.total_summary.return_value = {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "cost": 0.03}
    c.get_status.return_value = {
        "session": "test_sess", "messages": 5, "provider": "ollama",
        "model": "gemma4", "tools": 3, "servers": ["fs", "mem"],
    }
    c.session_id = "test_sess"
    c.history.async_load_session = AsyncMock(return_value=[
        {"role": "user", "content": "hi", "timestamp": "2024-01-01T12:00:00"},
        {"role": "assistant", "content": "hello", "timestamp": "2024-01-01T12:00:05"},
    ])
    c.history.async_list_sessions = AsyncMock(return_value=["sess1", "sess2", "test_sess"])
    return c


@pytest.fixture
def app(chat):
    return CliApp(chat)


def test_init(app):
    assert app._theme_mgr is not None
    assert app._session is None
    assert app._timestamps_enabled is False


def test_theme_property(app):
    t = app.T
    assert t is not None
    assert t.name.startswith("opencode")


def test_set_theme_same(app):
    result = app._set_theme("opencode")
    assert "Already" in result


def test_set_theme_switch(app):
    result = app._set_theme("cursor")
    assert "Switched" in result
    assert app.T.name == "cursor"


def test_set_theme_invalid(app):
    result = app._set_theme("nonexistent")
    assert "Unknown" in result
    assert app._theme_mgr.theme == "opencode"


def test_update_completer_no_session(app):
    app._update_completer()
    assert app._session is None


@patch("mcp_cli.ui.app.PromptSession")
def test_initialize_creates_session(MockSession, app):
    session = MagicMock()
    MockSession.return_value = session
    asyncio.run(app.initialize())
    assert app._session is not None
    MockSession.assert_called_once()


@patch("mcp_cli.ui.app.PromptSession")
def test_initialize_updates_completer(MockSession, app):
    session = MagicMock()
    MockSession.return_value = session
    asyncio.run(app.initialize())
    assert app._session.completer is not None


@patch("mcp_cli.ui.app.route_command")
@pytest.mark.asyncio
async def test_run_slash_command(mock_route, app):
    app._session = MagicMock()
    app._session.prompt_async = AsyncMock(side_effect=["/help", EOFError()])
    mock_route.return_value = (True, "Help text")
    with patch.object(app, "_print_help"):
        await app.run()
    mock_route.assert_called()


def test_print_usage(app, capsys):
    app._print_usage()
    captured = capsys.readouterr()
    assert "Input tokens" in captured.out
    assert "100" in captured.out or "1,000" in captured.out


def test_print_status(app, capsys):
    app._print_status()
    captured = capsys.readouterr()
    assert "test_sess" in captured.out


def test_format_timestamp_disabled(app):
    assert app._format_timestamp("2024-01-01T12:00:00") == ""


def test_format_timestamp_enabled(app):
    app._timestamps_enabled = True
    result = app._format_timestamp("2024-01-01T12:00:00")
    assert "12:00:00" in result


def test_format_timestamp_empty(app):
    app._timestamps_enabled = True
    assert app._format_timestamp("") == ""


def test_format_timestamp_invalid(app):
    app._timestamps_enabled = True
    assert app._format_timestamp("not-a-date") == ""


@pytest.mark.asyncio
async def test_handle_history(app, chat, capsys):
    await app._handle_history("test_sess")
    captured = capsys.readouterr()
    assert "test_sess" in captured.out


@pytest.mark.asyncio
async def test_handle_history_empty(app, chat, capsys):
    chat.history.async_load_session = AsyncMock(return_value=[])
    await app._handle_history("empty_sess")
    captured = capsys.readouterr()
    assert "No messages" in captured.out


@pytest.mark.asyncio
async def test_handle_list_sessions(app, chat, capsys):
    await app._handle_list_sessions()
    captured = capsys.readouterr()
    assert "sess1" in captured.out


@pytest.mark.asyncio
async def test_handle_list_sessions_empty(app, chat, capsys):
    chat.history.async_list_sessions = AsyncMock(return_value=[])
    await app._handle_list_sessions()
    captured = capsys.readouterr()
    assert "No saved sessions" in captured.out


@pytest.mark.asyncio
async def test_handle_switch_session(app, chat):
    await app._handle_switch_session("new_sess")
    assert chat.session_id == "new_sess"


@pytest.mark.asyncio
async def test_handle_switch_session_missing_id(app, chat, capsys):
    await app._handle_switch_session("")
    captured = capsys.readouterr()
    assert "Usage" in captured.out


@pytest.mark.asyncio
async def test_handle_search(app, chat, capsys):
    chat.history.search = MagicMock(return_value=[
        {"role": "user", "content": "test query", "timestamp": "2024-01-01T12:00:00"},
    ])
    await app._handle_search("query")
    captured = capsys.readouterr()
    assert "test query" in captured.out


@pytest.mark.asyncio
async def test_handle_search_no_timestamp(app, chat, capsys):
    chat.history.search = MagicMock(return_value=[
        {"role": "assistant", "content": "response", "timestamp": ""},
    ])
    await app._handle_search("q")
    captured = capsys.readouterr()
    assert "response" in captured.out


def test_print_help(app, capsys):
    app._print_help()
    captured = capsys.readouterr()
    assert "/help" in captured.out
    assert "/tools" in captured.out


def test_print_help_contains_themes(app, capsys):
    app._print_help()
    captured = capsys.readouterr()
    assert "opencode" in captured.out
    assert "cursor" in captured.out
    assert "opencode" in captured.out


def test_prompt_timeout_env(monkeypatch):
    monkeypatch.setenv("PROMPT_TIMEOUT", "30")
    app = CliApp(MagicMock())
    assert app._prompt_timeout == 30.0


def test_prompt_timeout_default():
    app = CliApp(MagicMock())
    assert app._prompt_timeout == 0.0
