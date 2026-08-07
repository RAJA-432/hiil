from __future__ import annotations

import asyncio

import pytest

import setu_bridge.connection as conn_module
from setu_bridge.connection import ManagedConnection


class _FakeAsyncCM:
    def __init__(self, value) -> None:
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc):
        return False


class _FakeClientSession:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FailingSession(_FakeClientSession):
    async def initialize(self):
        raise RuntimeError("handshake failed")


class _SlowSession(_FakeClientSession):
    async def initialize(self):
        await asyncio.sleep(10)


def _patch_stdio(monkeypatch, session_cls):
    monkeypatch.setattr(
        conn_module, "stdio_client", lambda params: _FakeAsyncCM((object(), object()))
    )
    monkeypatch.setattr(conn_module, "ClientSession", session_cls)


async def test_connect_tears_down_exit_stack_on_handshake_failure(monkeypatch) -> None:
    calls = []
    original_aclose = conn_module.AsyncExitStack.aclose

    async def spy_aclose(self):
        calls.append(True)
        return await original_aclose(self)

    monkeypatch.setattr(conn_module.AsyncExitStack, "aclose", spy_aclose)
    _patch_stdio(monkeypatch, _FailingSession)

    conn = ManagedConnection(command="python", args=["-m", "setu_bridge.mock_mail"])

    with pytest.raises(RuntimeError, match="handshake failed"):
        await conn.connect()

    assert calls == [True]
    assert conn._session is None


async def test_connect_times_out_when_initialize_hangs(monkeypatch) -> None:
    calls = []
    original_aclose = conn_module.AsyncExitStack.aclose

    async def spy_aclose(self):
        calls.append(True)
        return await original_aclose(self)

    monkeypatch.setattr(conn_module.AsyncExitStack, "aclose", spy_aclose)
    _patch_stdio(monkeypatch, _SlowSession)

    conn = ManagedConnection(
        command="python", args=["-m", "setu_bridge.mock_mail"], connect_timeout=0.1
    )

    with pytest.raises(TimeoutError):
        await conn.connect()

    assert calls == [True]
    assert conn._session is None


async def test_connect_success_keeps_session(monkeypatch) -> None:
    class _OkSession(_FakeClientSession):
        async def initialize(self):
            return None

    _patch_stdio(monkeypatch, _OkSession)

    conn = ManagedConnection(command="python", args=["-m", "setu_bridge.mock_mail"])

    await conn.connect()

    assert conn._session is not None
    await conn.cleanup()
    assert conn._session is None
