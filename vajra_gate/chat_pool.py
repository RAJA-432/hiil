import asyncio
from collections import OrderedDict
from contextlib import AsyncExitStack
from typing import Any


class _PooledChat:
    """Session-scoped proxy around a CliChat that serializes send() calls."""

    def __init__(self, chat: Any, lock: asyncio.Lock) -> None:
        object.__setattr__(self, "_chat", chat)
        object.__setattr__(self, "_lock", lock)

    async def send(self, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            return await self._chat.send(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._chat, name, value)


class ChatPool:
    """Pool of isolated per-session chat instances sharing one set of MCP servers."""

    def __init__(self, maxsize: int = 32, builder: Any = None) -> None:
        self._maxsize = maxsize
        self._entries: OrderedDict[str, _PooledChat] = OrderedDict()
        self._active = "default"
        self._builder: Any = builder
        self._stack: AsyncExitStack | None = None
        self._init_lock = asyncio.Lock()
        self._lock = asyncio.Lock()

    @property
    def active(self) -> str:
        return self._active

    async def init(self, logging_callback: Any = None) -> None:
        async with self._init_lock:
            if self._builder is not None:
                return
            from mcp_cli.services.factory import create_chat_factory
            stack = AsyncExitStack()
            self._builder = await create_chat_factory(stack, logging_callback=logging_callback)
            self._stack = stack

    async def get(self, session_id: str) -> _PooledChat:
        await self.init()
        entry = self._entries.get(session_id)
        if entry is not None:
            self._entries.move_to_end(session_id)
            return entry
        chat = await self._builder.create(session_id)
        duplicate = False
        async with self._lock:
            existing = self._entries.get(session_id)
            if existing is not None:
                self._entries.move_to_end(session_id)
                entry = existing
                duplicate = True
            else:
                entry = _PooledChat(chat, asyncio.Lock())
                self._entries[session_id] = entry
        if duplicate:
            await self._close_chat(chat)
        await self._evict_lru()
        return entry

    async def new_session(self) -> str:
        await self.init()
        from datetime import datetime
        sid = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        chat = await self._builder.create(sid)
        async with self._lock:
            self._entries[sid] = _PooledChat(chat, asyncio.Lock())
            self._active = sid
        await self._evict_lru()
        return sid

    async def set_active(self, session_id: str) -> None:
        async with self._lock:
            self._active = session_id

    async def evict(self, session_id: str) -> None:
        async with self._lock:
            entry = self._entries.pop(session_id, None)
        if entry is not None:
            await self._close_entry(entry)

    async def aclose(self) -> None:
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
        for entry in entries:
            await self._close_entry(entry)
        stack, self._stack = self._stack, None
        self._builder = None
        if stack is not None:
            await stack.aclose()

    async def _evict_lru(self) -> None:
        while True:
            async with self._lock:
                if len(self._entries) <= self._maxsize:
                    return
                _, entry = self._entries.popitem(last=False)
            await self._close_entry(entry)

    async def _close_entry(self, entry: _PooledChat) -> None:
        async with entry._lock:
            await self._close_chat(entry._chat)

    @staticmethod
    async def _close_chat(chat: Any) -> None:
        task = getattr(chat, "_auto_index_task", None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, RuntimeError):
                pass
        for name in ("history", "usage", "vector_store"):
            store = getattr(chat, name, None)
            close = getattr(store, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass
