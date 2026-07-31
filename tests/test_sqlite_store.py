from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from mcp_cli.services import sqlite_store
from mcp_cli.services.history import ChatHistoryManager


def test_async_wrapper_returns_correct_values(tmp_path):
    manager = ChatHistoryManager(str(tmp_path / "chat.db"))

    async def run():
        await manager.async_save_message("s1", "user", "hello")
        return await manager.async_load_session("s1")

    rows = asyncio.run(run())
    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "hello"


def test_concurrent_async_writes_do_not_corrupt_data(tmp_path):
    manager = ChatHistoryManager(str(tmp_path / "chat.db"))

    async def run():
        await asyncio.gather(
            *(manager.async_save_message("s1", "user", f"m{i}") for i in range(50))
        )
        return await manager.async_load_session("s1")

    rows = asyncio.run(run())
    assert len(rows) == 50
    assert {row["content"] for row in rows} == {f"m{i}" for i in range(50)}


def test_asyncify_uses_shared_executor():
    assert isinstance(sqlite_store._EXECUTOR, ThreadPoolExecutor)
    assert sqlite_store._EXECUTOR._max_workers == 8
