from unittest.mock import AsyncMock

import pytest

from mcp_cli.commands.servers import handle_load, handle_reload, handle_unload


@pytest.mark.asyncio
async def test_load_missing_script():
    chat = AsyncMock()
    reply = await handle_load(chat, "")
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_handle_load_success():
    chat = AsyncMock()
    chat.add_server = AsyncMock(return_value="Loaded server_id from script.py")
    reply = await handle_load(chat, "script.py")
    assert "Loaded" in reply
    chat.add_server.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_with_id():
    chat = AsyncMock()
    chat.add_server = AsyncMock(return_value="Loaded my_id from script.py")
    reply = await handle_load(chat, "script.py my_id")
    chat.add_server.assert_awaited_with("my_id", "script.py")


@pytest.mark.asyncio
async def test_unload_missing_id():
    chat = AsyncMock()
    reply = await handle_unload(chat, "")
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_unload_success():
    chat = AsyncMock()
    chat.remove_server = AsyncMock(return_value="Unloaded srv1")
    reply = await handle_unload(chat, "srv1")
    assert "Unloaded" in reply
    chat.remove_server.assert_awaited_with("srv1")


@pytest.mark.asyncio
async def test_reload_missing_parts():
    chat = AsyncMock()
    reply = await handle_reload(chat, "")
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_reload_with_script():
    chat = AsyncMock()
    chat.reload_server = AsyncMock(return_value="Reloaded srv1 from new.py")
    reply = await handle_reload(chat, "srv1 new.py")
    chat.reload_server.assert_awaited_with("srv1", "new.py")


@pytest.mark.asyncio
async def test_reload_fallback_to_client_script():
    chat = AsyncMock()
    chat.clients = {"myserver": type("obj", (object,), {"script": "myserver.py"})()}
    chat.reload_server = AsyncMock(return_value="Reloaded myserver")
    reply = await handle_reload(chat, "myserver")
    chat.reload_server.assert_awaited_with("myserver", "myserver.py")


@pytest.mark.asyncio
async def test_reload_fallback_not_found():
    chat = AsyncMock()
    chat.clients = {}
    chat.reload_server = AsyncMock(return_value="Reloaded")
    reply = await handle_reload(chat, "nonexistent")
    assert "not found" in reply
