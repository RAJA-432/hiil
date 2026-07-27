from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp import types

from setu_bridge import SetuBridge


@pytest.mark.asyncio
async def test_mcp_client_session_uninitialized():
    client = SetuBridge(command="python", args=["server.py"])
    with pytest.raises(ConnectionError, match="Client session not initialized"):
        client.session()

@pytest.mark.asyncio
async def test_mcp_client_list_tools():
    client = SetuBridge(command="python", args=["server.py"])
    mock_session = AsyncMock()
    mock_session.list_tools.return_value = MagicMock(tools=[types.Tool(name="test_tool", description="test", inputSchema={})])
    client._conn._session = mock_session

    tools = await client.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "test_tool"
    mock_session.list_tools.assert_called_once()

@pytest.mark.asyncio
async def test_mcp_client_call_tool():
    client = SetuBridge(command="python", args=["server.py"])
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = MagicMock(content=[])
    client._conn._session = mock_session

    await client.call_tool("test_tool", {"arg": "val"})
    mock_session.call_tool.assert_called_with("test_tool", {"arg": "val"})
