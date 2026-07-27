from unittest.mock import AsyncMock, patch

import pytest

from mcp_cli.services.server_manager import load_mcp_server


@pytest.mark.asyncio
async def test_load_mcp_server_default():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "test_server.py")

        MockClient.assert_called_once()
        args, kwargs = MockClient.call_args
        assert kwargs["command"] == "python"
        assert kwargs["args"][:1] == ["test_server.py"]
        assert kwargs["args"][1:3] == ["--transport", "sse"]
        assert "--port" in kwargs["args"]
        instance.connect.assert_awaited_once()
        assert result == instance


@pytest.mark.asyncio
async def test_load_mcp_server_with_uv(monkeypatch):
    monkeypatch.setenv("USE_UV", "1")
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "test_server.py")

        args, kwargs = MockClient.call_args
        assert kwargs["command"] == "uv"
        assert kwargs["args"][:2] == ["run", "test_server.py"]
        assert kwargs["args"][2:4] == ["--transport", "sse"]
        assert "--port" in kwargs["args"]
        assert result == instance


@pytest.mark.asyncio
async def test_load_mcp_server_with_args():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "server.py", args=["--port", "8080"])

        args, kwargs = MockClient.call_args
        assert "--port" in kwargs["args"]
        assert "8080" in kwargs["args"]


@pytest.mark.asyncio
async def test_load_mcp_server_with_env():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "server.py", env={"KEY": "VAL"})

        args, kwargs = MockClient.call_args
        assert kwargs["env"] == {"KEY": "VAL"}
