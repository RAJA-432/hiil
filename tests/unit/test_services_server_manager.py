from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, patch

import pytest

from mcp_cli.config import ServerConfig
from mcp_cli.services.server_manager import (
    _exc_message,
    _find_free_port,
    create_servers,
    load_mcp_server,
)


class _CtxWrap:
    """Wraps an inner value as a proper async context manager.

    ``__aenter__`` returns *value* so that
    ``await stack.enter_async_context(wrap)`` produces *value*.
    """

    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args) -> None:
        pass


# ── _find_free_port ──────────────────────────────────────────────────


def test_find_free_port_returns_first_free():
    with patch("mcp_cli.services.server_manager.socket.socket") as mock_cls:
        sock = mock_cls.return_value
        sock.__enter__.return_value = sock
        sock.bind.return_value = None

        port = _find_free_port(8100)

    assert port == 8100
    sock.bind.assert_called_once_with(("127.0.0.1", 8100))


def test_find_free_port_retries_on_busy_port():
    with patch("mcp_cli.services.server_manager.socket.socket") as mock_cls:
        sock = mock_cls.return_value
        sock.__enter__.return_value = sock
        sock.bind.side_effect = [OSError("in use"), None]

        port = _find_free_port(8100)

    assert port == 8101
    assert sock.bind.call_count == 2


# ── load_mcp_server – default (sse), streamable-http & stdio transports ────


@pytest.mark.asyncio
async def test_load_mcp_server_default():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "test_server.py")

        MockClient.assert_called_once()
        _, kwargs = MockClient.call_args
        assert kwargs["command"] == "python"
        assert kwargs["args"][:1] == ["test_server.py"]
        assert kwargs["args"][1:3] == ["--transport", "sse"]
        assert "--port" in kwargs["args"]
        assert result == instance


@pytest.mark.asyncio
async def test_load_mcp_server_with_uv(monkeypatch):
    monkeypatch.setenv("USE_UV", "1")
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "test_server.py")

        _, kwargs = MockClient.call_args
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

        _, kwargs = MockClient.call_args
        assert "--port" in kwargs["args"]
        assert "8080" in kwargs["args"]


@pytest.mark.asyncio
async def test_load_mcp_server_with_env():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "server.py", env={"KEY": "VAL"})

        _, kwargs = MockClient.call_args
        assert kwargs["env"] == {"KEY": "VAL"}


@pytest.mark.asyncio
async def test_load_mcp_server_streamable_http():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server(
            "test_id", "test_server.py", transport="streamable-http"
        )

        MockClient.assert_called_once()
        _, kwargs = MockClient.call_args
        assert kwargs["transport"] == "streamable-http"
        assert kwargs["url"].endswith("/mcp")
        assert "--transport" in kwargs["args"]
        assert "streamable-http" in kwargs["args"]
        assert "--port" in kwargs["args"]
        assert result is instance


@pytest.mark.asyncio
async def test_load_mcp_server_stdio():
    with patch("mcp_cli.services.server_manager.SetuBridge") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance

        result = await load_mcp_server("test_id", "test_server.py", transport="stdio")

        MockClient.assert_called_once()
        _, kwargs = MockClient.call_args
        assert kwargs["transport"] == "stdio"
        assert "url" not in kwargs
        assert "--transport" not in kwargs["args"]
        assert "--port" not in kwargs["args"]
        assert result is instance


# ── _exc_message ────────────────────────────────────────────────────


def test_exc_message_baseexceptiongroup():
    inner = ValueError("inner error")
    exc = BaseExceptionGroup("group", [inner])
    assert _exc_message(exc) == "inner error"


def test_exc_message_empty_message():
    exc = ValueError("")
    assert _exc_message(exc) == "ValueError"


def test_exc_message_normal():
    exc = ValueError("something went wrong")
    assert _exc_message(exc) == "something went wrong"


# ── create_servers ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_servers_doc_server_success():
    doc_inner = AsyncMock()

    async def _load_side_effect(sid, script, **kw):
        return _CtxWrap(doc_inner)

    with patch("mcp_cli.services.server_manager.load_mcp_server") as mock_load:
        mock_load.side_effect = _load_side_effect
        stack = AsyncExitStack()
        doc_client, clients = await create_servers([], stack)

    assert doc_client is doc_inner
    assert clients == {}


@pytest.mark.asyncio
async def test_create_servers_doc_server_failure():
    async def _load_side_effect(sid, script, **kw):
        raise RuntimeError("doc server failed")

    with (
        patch("mcp_cli.services.server_manager.load_mcp_server") as mock_load,
        patch("mcp_cli.services.server_manager.logger") as mock_logger,
    ):
        mock_load.side_effect = _load_side_effect
        stack = AsyncExitStack()
        doc_client, clients = await create_servers([], stack)

    assert doc_client is None
    assert clients == {}
    mock_logger.warning.assert_called_once()
    assert "doc server" in mock_logger.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_create_servers_loads_multiple_servers():
    doc_inner = AsyncMock()
    helper_a = AsyncMock()
    helper_b = AsyncMock()

    async def _load_side_effect(sid, script, **kw):
        if script == "mcp_server":
            return _CtxWrap(doc_inner)
        if sid == "server_a":
            return _CtxWrap(helper_a)
        return _CtxWrap(helper_b)

    with (
        patch("mcp_cli.services.server_manager.load_mcp_server") as mock_load,
        patch("mcp_cli.services.server_manager.logger"),
    ):
        mock_load.side_effect = _load_side_effect
        stack = AsyncExitStack()
        cfgs = [
            ServerConfig(id="server_a", script="a.py"),
            ServerConfig(id="server_b", script="b.py"),
        ]
        doc_client, clients = await create_servers(cfgs, stack)

    assert doc_client is doc_inner
    assert clients == {"server_a": helper_a, "server_b": helper_b}


@pytest.mark.asyncio
async def test_create_servers_one_server_fails():
    doc_inner = AsyncMock()
    helper_inner = AsyncMock()

    async def _load_side_effect(sid, script, **kw):
        if script == "mcp_server":
            return _CtxWrap(doc_inner)
        if sid == "fail":
            raise RuntimeError("fail server crashed")
        return _CtxWrap(helper_inner)

    with (
        patch("mcp_cli.services.server_manager.load_mcp_server") as mock_load,
        patch("mcp_cli.services.server_manager.logger") as mock_logger,
    ):
        mock_load.side_effect = _load_side_effect
        stack = AsyncExitStack()
        cfgs = [
            ServerConfig(id="fail", script="fail.py"),
            ServerConfig(id="ok", script="ok.py"),
        ]
        doc_client, clients = await create_servers(cfgs, stack)

    assert doc_client is doc_inner
    assert "fail" not in clients
    assert clients["ok"] is helper_inner
    assert mock_logger.warning.call_count >= 1
