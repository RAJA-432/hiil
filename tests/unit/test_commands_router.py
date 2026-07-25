from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cli.commands.router import route_command, route_tool_command
from mcp_cli.locales import set_lang


@pytest.mark.asyncio
async def test_route_exit():
    cont, reply = await route_command("/exit", None)
    assert cont is False
    assert reply is None


@pytest.mark.asyncio
async def test_route_quit():
    cont, reply = await route_command("/quit", None)
    assert cont is False


@pytest.mark.asyncio
async def test_route_help():
    app = MagicMock()
    cont, reply = await route_command("/help", None, app)
    assert cont is True
    app._print_help.assert_called_once()


@pytest.mark.asyncio
async def test_route_tools():
    chat = MagicMock()
    chat.tools_by_name.keys.return_value = ["tool1"]
    cont, reply = await route_command("/tools", chat)
    assert cont is True


@pytest.mark.asyncio
async def test_route_theme_no_arg():
    app = MagicMock()
    app._theme.name = "opencode"
    cont, reply = await route_command("/theme", None, app)
    assert cont is True


@pytest.mark.asyncio
async def test_route_theme_switch():
    app = MagicMock()
    app._set_theme.return_value = "Switched to cursor"
    cont, reply = await route_command("/theme cursor", None, app)
    assert reply == "Switched to cursor"


@pytest.mark.asyncio
async def test_route_load():
    chat = MagicMock()
    chat.add_server = AsyncMock(return_value="loaded")
    cont, reply = await route_command("/load script.py", chat)
    assert reply == "loaded"


@pytest.mark.asyncio
async def test_route_unload():
    chat = MagicMock()
    chat.remove_server = AsyncMock(return_value="unloaded")
    cont, reply = await route_command("/unload srv1", chat)
    assert reply == "unloaded"


@pytest.mark.asyncio
async def test_route_reload():
    chat = MagicMock()
    chat.reload_server = AsyncMock(return_value="reloaded")
    cont, reply = await route_command("/reload srv1 new.py", chat)
    assert reply == "reloaded"


@pytest.mark.asyncio
async def test_route_history():
    app = MagicMock()
    app._handle_history = AsyncMock()
    cont, reply = await route_command("/history sess1", None, app)
    app._handle_history.assert_awaited_with("sess1")


@pytest.mark.asyncio
async def test_route_sessions():
    app = MagicMock()
    app._handle_list_sessions = AsyncMock()
    cont, reply = await route_command("/sessions", None, app)
    app._handle_list_sessions.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_session():
    app = MagicMock()
    app._handle_switch_session = AsyncMock()
    cont, reply = await route_command("/session newid", None, app)
    app._handle_switch_session.assert_awaited()


@pytest.mark.asyncio
async def test_route_usage():
    app = MagicMock()
    cont, reply = await route_command("/usage", None, app)
    app._print_usage.assert_called_once()


@pytest.mark.asyncio
async def test_route_agent_respond_removed():
    chat = MagicMock()
    app = MagicMock()
    cont, reply = await route_command("/agent respond foo", chat, app)
    assert "removed" in reply


@pytest.mark.asyncio
async def test_route_agent_create():
    chat = MagicMock()
    app = MagicMock()
    app._session.prompt_async = AsyncMock(return_value="y")
    cont, reply = await route_command("/agent create test_agent", chat, app)
    assert cont is True


@pytest.mark.asyncio
async def test_route_tool_command():
    chat = MagicMock()
    chat.tools_by_name = {"my_tool": {"openai": {"function": {"parameters": {"properties": {}}}}}}
    chat.call_tool_by_name = AsyncMock(return_value="tool result")
    reply = await route_tool_command(chat, "my_tool arg1")
    assert reply == "tool result"


@pytest.mark.asyncio
async def test_route_tool_command_unknown():
    chat = MagicMock()
    chat.tools_by_name = {}
    reply = await route_tool_command(chat, "unknown_tool")
    assert "Unknown" in reply


@pytest.mark.asyncio
async def test_route_unknown_command():
    chat = MagicMock()
    chat.tools_by_name = {}
    cont, reply = await route_command("/nonexistent", chat)
    assert "Unknown" in reply


@pytest.mark.asyncio
async def test_route_model_show():
    chat = MagicMock()
    chat.claude.model = "test-model"
    chat.claude.list_models = AsyncMock(return_value=[])
    cont, reply = await route_command("/model", chat)
    assert "test-model" in reply


@pytest.mark.asyncio
async def test_route_model_switch():
    chat = MagicMock()
    chat.claude.update_model = MagicMock(return_value="Model switched to 'new-model'.")
    chat.refresh_system_prompt = MagicMock()
    cont, reply = await route_command("/model new-model", chat)
    chat.claude.update_model.assert_called_with("new-model")
    chat.refresh_system_prompt.assert_called_once()


@pytest.mark.asyncio
async def test_route_provider_show():
    chat = MagicMock()
    chat.claude.provider = "ollama"
    cont, reply = await route_command("/provider", chat)
    assert "ollama" in reply


@pytest.mark.asyncio
async def test_route_provider_switch():
    chat = MagicMock()
    chat.claude.api_key = ""
    chat.claude.model = "gpt-4o-mini"
    chat.claude.list_models = AsyncMock(return_value=[])
    cont, reply = await route_command("/provider ollama", chat)
    assert "ollama" in reply


@pytest.mark.asyncio
async def test_route_models():
    chat = MagicMock()
    chat.claude.list_models = AsyncMock(return_value=[{"id": "model1"}, {"id": "model2"}])
    cont, reply = await route_command("/models", chat)
    assert "model1" in reply
    assert "model2" in reply


@pytest.mark.asyncio
async def test_route_semsearch():
    chat = MagicMock()
    chat.semantic_search = AsyncMock(return_value=[
        {"key": "k1", "text": "hello world", "score": 0.95},
    ])
    cont, reply = await route_command("/semsearch hello", chat)
    assert "0.95" in reply
    assert "hello world" in reply


@pytest.mark.asyncio
async def test_route_semsearch_no_results():
    chat = MagicMock()
    chat.semantic_search = AsyncMock(return_value=[])
    cont, reply = await route_command("/semsearch nothing", chat)
    assert "No semantic matches" in reply


@pytest.mark.asyncio
async def test_route_semsearch_missing_query():
    chat = MagicMock()
    cont, reply = await route_command("/semsearch", chat)
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_route_models_unavailable():
    chat = MagicMock()
    chat.claude.list_models = AsyncMock(return_value=[])
    cont, reply = await route_command("/models", chat)
    assert "Could not fetch" in reply


@pytest.mark.asyncio
async def test_route_key_status():
    chat = MagicMock()
    chat.claude.provider = "test_prov"
    with patch("mcp_cli.commands.router.async_load_api_key", AsyncMock(return_value="sk-existing")):
        cont, reply = await route_command("/key status", chat)
    assert cont is True


@pytest.mark.asyncio
async def test_route_key_set():
    chat = MagicMock()
    with patch("mcp_cli.commands.router.async_save_api_key", AsyncMock()) as mock_save:
        cont, reply = await route_command("/key set my_prov sk-abc", chat)
        mock_save.assert_called_once_with("my_prov", "sk-abc")
        assert "saved" in reply


@pytest.mark.asyncio
async def test_route_key_set_missing_args():
    chat = MagicMock()
    cont, reply = await route_command("/key set", chat)
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_route_key_delete():
    chat = MagicMock()
    with patch("mcp_cli.commands.router.async_delete_api_key", AsyncMock(return_value=True)) as mock_del:
        cont, reply = await route_command("/key delete test_prov", chat)
        mock_del.assert_called_once_with("test_prov")
        assert "deleted" in reply


@pytest.mark.asyncio
async def test_route_key_delete_nonexistent():
    chat = MagicMock()
    with patch("mcp_cli.commands.router.async_delete_api_key", AsyncMock(return_value=False)) as mock_del:
        cont, reply = await route_command("/key delete test_prov", chat)
        assert "No stored key" in reply


@pytest.mark.asyncio
async def test_route_key_no_subcommand():
    chat = MagicMock()
    chat.claude.provider = "test_prov"
    with patch("mcp_cli.commands.router.async_load_api_key", AsyncMock(return_value="sk-some")):
        cont, reply = await route_command("/key", chat)
    assert "Stored key" in reply


@pytest.mark.asyncio
async def test_route_key_status_with_stored_key():
    chat = MagicMock()
    chat.claude.provider = "test_prov"
    with patch("mcp_cli.commands.router.async_load_api_key", AsyncMock(return_value="sk-abc123xyz-extra-long")):
        cont, reply = await route_command("/key status", chat)
        assert "sk-abc12" in reply


@pytest.mark.asyncio
async def test_route_key_status_no_key():
    chat = MagicMock()
    chat.claude.provider = "test_prov"
    with patch("mcp_cli.commands.router.async_load_api_key", AsyncMock(return_value=None)):
        cont, reply = await route_command("/key status", chat)
        assert "No stored key" in reply


@pytest.mark.asyncio
async def test_route_timer_start():
    chat = MagicMock()
    cont, reply = await route_command("/timer start", chat)
    assert "Timer started" in reply
    assert hasattr(chat, "_timer_start")


@pytest.mark.asyncio
async def test_route_timer_status_no_timer():
    cont, reply = await route_command("/timer", MagicMock())
    assert "No timer running" in reply


@patch("mcp_cli.commands.router.set_lang")
@pytest.mark.asyncio
async def test_route_lang_switch(mock_set_lang):
    mock_set_lang.return_value = "English"
    app = MagicMock()
    cont, reply = await route_command("/lang en", None, app)
    assert "Switched" in reply


@pytest.mark.asyncio
async def test_route_lang_show():
    set_lang("en")
    cont, reply = await route_command("/lang", None)
    assert "Current language" in reply
    assert "English" in reply


@pytest.mark.asyncio
async def test_route_new():
    chat = MagicMock()
    chat.new_session = MagicMock(return_value="session_20260101_120000")
    app = MagicMock()
    cont, reply = await route_command("/new", chat, app)
    assert "session_20260101_120000" in reply


@pytest.mark.asyncio
async def test_route_rename():
    chat = MagicMock()
    chat.history.async_rename_session = AsyncMock(return_value=True)
    chat.session_id = "old_sess"
    cont, reply = await route_command("/rename new_name", chat, app=None)
    assert "renamed" in reply
    assert "old_sess" in reply
    assert "new_name" in reply


@pytest.mark.asyncio
async def test_route_rename_no_arg():
    chat = MagicMock()
    cont, reply = await route_command("/rename", chat)
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_route_rename_not_found():
    chat = MagicMock()
    chat.history.async_rename_session = AsyncMock(return_value=False)
    cont, reply = await route_command("/rename new_name", chat)
    assert "not found" in reply


@pytest.mark.asyncio
async def test_route_fork():
    chat = MagicMock()
    chat.history.async_fork_session = AsyncMock(return_value=3)
    chat.history.async_load_session = AsyncMock(return_value=[{"role": "user", "content": "hi"}])
    cont, reply = await route_command("/fork sess_a", chat, app=MagicMock())
    assert "Forked" in reply
    assert "3" in reply


@pytest.mark.asyncio
async def test_route_fork_no_arg():
    chat = MagicMock()
    cont, reply = await route_command("/fork", chat)
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_route_fork_not_found():
    chat = MagicMock()
    chat.history.async_fork_session = AsyncMock(return_value=0)
    cont, reply = await route_command("/fork nonexistent", chat)
    assert "not found" in reply


@pytest.mark.asyncio
async def test_route_search():
    chat = MagicMock()
    chat.history.async_search_messages = AsyncMock(return_value=[{"line": 1, "content": "hello world"}])
    app = MagicMock()
    cont, reply = await route_command("/search hello", chat, app)
    assert cont is True


@pytest.mark.asyncio
async def test_route_search_no_arg():
    chat = MagicMock()
    cont, reply = await route_command("/search", chat)
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_route_search_no_matches():
    chat = MagicMock()
    chat.history.async_search_messages = AsyncMock(return_value=[])
    cont, reply = await route_command("/search zzz_nonexistent", chat)
    assert "No matches" in reply


@pytest.mark.asyncio
async def test_route_undo():
    chat = MagicMock()
    chat.history.async_undo_last_messages = AsyncMock(return_value=2)
    chat.history.async_load_session = AsyncMock(return_value=[{"role": "user", "content": "remaining"}])
    cont, reply = await route_command("/undo", chat)
    assert "Removed" in reply
    assert "2" in reply


@pytest.mark.asyncio
async def test_route_undo_nothing():
    chat = MagicMock()
    chat.history.async_undo_last_messages = AsyncMock(return_value=0)
    cont, reply = await route_command("/undo", chat)
    assert "Nothing to undo" in reply


@pytest.mark.asyncio
async def test_route_compact():
    chat = MagicMock()
    chat.messages = [{"role": "user", "content": f"msg_{i}"} for i in range(10)]
    cont, reply = await route_command("/compact", chat)
    assert "compacted" in reply
    assert "10" in reply
    assert len(chat.messages) < 10


@pytest.mark.asyncio
async def test_compact_too_few_messages():
    chat = MagicMock()
    chat.messages = [{"role": "user", "content": "hi"}]
    cont, reply = await route_command("/compact", chat)
    assert "Too few" in reply


@pytest.mark.asyncio
async def test_route_export():
    chat = MagicMock()
    chat.export_transcript = MagicMock(return_value="transcript content")
    with patch("builtins.open", MagicMock()) as mock_open:
        cont, reply = await route_command("/export", chat)
        assert "exported" in reply


@pytest.mark.asyncio
async def test_route_export_failure():
    chat = MagicMock()
    chat.export_transcript = MagicMock(return_value="content")
    with patch("builtins.open", MagicMock(side_effect=PermissionError("denied"))):
        cont, reply = await route_command("/export", chat)
        assert "failed" in reply


@pytest.mark.asyncio
async def test_route_copy():
    chat = MagicMock()
    chat.get_last_assistant_message = MagicMock(return_value="last response")
    cont, reply = await route_command("/copy", chat)
    assert "chars" in reply


@pytest.mark.asyncio
async def test_route_copy_no_message():
    chat = MagicMock()
    chat.get_last_assistant_message = MagicMock(return_value=None)
    cont, reply = await route_command("/copy", chat)
    assert "No assistant message" in reply


@pytest.mark.asyncio
async def test_route_status():
    chat = MagicMock()
    app = MagicMock()
    cont, reply = await route_command("/status", chat, app)
    app._print_status.assert_called_once()


@pytest.mark.asyncio
async def test_route_timestamp():
    chat = MagicMock()
    app = MagicMock()
    app._timestamps_enabled = False
    cont, reply = await route_command("/timestamp", chat, app)
    assert "on" in reply
    assert app._timestamps_enabled is True


@pytest.mark.asyncio
async def test_route_timestamp_toggle():
    chat = MagicMock()
    app = MagicMock()
    app._timestamps_enabled = True
    cont, reply = await route_command("/timestamp", chat, app)
    assert "off" in reply
    assert app._timestamps_enabled is False
