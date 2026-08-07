import asyncio
from types import SimpleNamespace

import pytest

from vajra_gate.chat_pool import ChatPool


class FakeCloser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeHistoryStore:
    def __init__(self, messages: list[dict] | None = None, sessions: list[str] | None = None) -> None:
        self.messages = messages or []
        self.sessions = sessions or []
        self.closed = False

    async def async_load_session(self, session_id: str) -> list[dict]:
        return list(self.messages)

    async def async_delete_session(self, session_id: str) -> None:
        return None

    async def async_list_sessions(self) -> list[str]:
        return list(self.sessions)

    def close(self) -> None:
        self.closed = True


class FakeChat:
    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self.messages: list[str] = []
        self._auto_index_task: asyncio.Task | None = None
        self.history = FakeHistoryStore()
        self.usage = FakeCloser()
        self.vector_store = FakeCloser()

    async def send(self, text: str, **kwargs: object) -> str:
        self.messages.append(text)
        return f"reply:{text}@{self.session_id}"


class FakeBuilder:
    def __init__(self, chat_cls: type[FakeChat] = FakeChat) -> None:
        self.chat_cls = chat_cls
        self.chats: list[FakeChat] = []

    async def create(self, session_id: str = "default") -> FakeChat:
        chat = self.chat_cls(session_id)
        self.chats.append(chat)
        return chat


class GatedChat(FakeChat):
    def __init__(self, session_id: str = "default") -> None:
        super().__init__(session_id)
        self.enters: list[str] = []
        self._entered = asyncio.Event()
        self._release = asyncio.Event()

    async def send(self, text: str, **kwargs: object) -> str:
        self.messages.append(text)
        self.enters.append(text)
        self._entered.set()
        await asyncio.wait_for(self._release.wait(), timeout=5)
        return f"reply:{text}@{self.session_id}"


class FakeStack:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class TestPoolIsolation:
    async def test_different_sessions_run_concurrently_without_crossed_state(self) -> None:
        builder = FakeBuilder(GatedChat)
        pool = ChatPool(builder=builder)
        a = await pool.get("session_a")
        b = await pool.get("session_b")

        task_a = asyncio.create_task(a.send("question-a"))
        await asyncio.wait_for(builder.chats[0]._entered.wait(), timeout=2)
        task_b = asyncio.create_task(b.send("question-b"))
        await asyncio.wait_for(builder.chats[1]._entered.wait(), timeout=2)

        assert builder.chats[0].enters == ["question-a"]
        assert builder.chats[1].enters == ["question-b"]

        for chat in builder.chats:
            chat._release.set()
        results = await asyncio.gather(task_a, task_b)

        assert results == ["reply:question-a@session_a", "reply:question-b@session_b"]
        assert a._chat is not b._chat
        assert a._chat.session_id == "session_a"
        assert b._chat.session_id == "session_b"
        assert builder.chats[0].messages == ["question-a"]
        assert builder.chats[1].messages == ["question-b"]

    async def test_same_session_sends_are_serialized(self) -> None:
        builder = FakeBuilder(GatedChat)
        pool = ChatPool(builder=builder)
        a = await pool.get("session_a")
        chat = builder.chats[0]

        first = asyncio.create_task(a.send("first"))
        await asyncio.wait_for(chat._entered.wait(), timeout=2)
        second = asyncio.create_task(a.send("second"))

        await asyncio.sleep(0.05)
        assert chat.enters == ["first"]

        chat._release.set()
        assert await first == "reply:first@session_a"
        for _ in range(100):
            if len(chat.enters) == 2:
                break
            await asyncio.sleep(0.01)
        assert chat.enters == ["first", "second"]
        chat._release.set()
        assert await second == "reply:second@session_a"

    async def test_lru_eviction_closes_instance_not_shared_stack(self) -> None:
        builder = FakeBuilder()
        pool = ChatPool(maxsize=2, builder=builder)
        pool._stack = FakeStack()

        a = await pool.get("a")
        b = await pool.get("b")
        c = await pool.get("c")

        assert "a" not in pool._entries
        assert "b" in pool._entries
        assert "c" in pool._entries
        assert builder.chats[0].history.closed
        assert builder.chats[0].usage.closed
        assert builder.chats[0].vector_store.closed
        assert not builder.chats[1].history.closed
        assert not builder.chats[2].history.closed
        assert not pool._stack.closed

        fresh = await pool.get("a")
        assert fresh._chat is not a._chat

    async def test_evict_removes_and_closes_instance(self) -> None:
        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        a = await pool.get("session_x")

        await pool.evict("session_x")

        assert "session_x" not in pool._entries
        assert builder.chats[0].history.closed
        fresh = await pool.get("session_x")
        assert fresh._chat is not a._chat

    async def test_aclose_closes_instances_and_shared_stack(self) -> None:
        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        pool._stack = FakeStack()
        stack = pool._stack

        await pool.get("a")
        await pool.get("b")

        await pool.aclose()

        assert pool._entries == {}
        assert builder.chats[0].history.closed
        assert builder.chats[1].history.closed
        assert stack.closed


class TestPoolSessionManagement:
    async def test_new_session_registers_fresh_active_instance(self) -> None:
        builder = FakeBuilder()
        pool = ChatPool(builder=builder)

        sid = await pool.new_session()

        assert sid.startswith("session_")
        assert pool.active == sid
        assert sid in pool._entries
        assert pool._entries[sid]._chat.session_id == sid

    async def test_set_active_updates_active_session(self) -> None:
        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        await pool.get("other")

        await pool.set_active("other")

        assert pool.active == "other"


class TestRouterWiring:
    def _patch_require_chat(self, monkeypatch: pytest.MonkeyPatch, pool: ChatPool) -> None:
        async def _require_chat(request, session_id=None):
            if session_id:
                return await pool.get(session_id)
            return await pool.get(pool.active)

        monkeypatch.setattr("vajra_gate.routers.sessions._require_chat", _require_chat)

    async def test_new_session_router_registers_pool_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vajra_gate.routers.sessions as sessions_router
        import vajra_gate.state as state_mod

        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        monkeypatch.setattr(state_mod, "_pool", pool)
        monkeypatch.setattr(state_mod, "_chat", None)
        self._patch_require_chat(monkeypatch, pool)

        resp = await sessions_router.new_session(SimpleNamespace())

        assert resp.session_id.startswith("session_")
        assert pool.active == resp.session_id
        assert resp.session_id in pool._entries
        assert state_mod._chat is pool._entries[resp.session_id]

    async def test_switch_session_router_operates_on_sid_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vajra_gate.routers.sessions as sessions_router
        import vajra_gate.state as state_mod

        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        monkeypatch.setattr(state_mod, "_pool", pool)
        monkeypatch.setattr(state_mod, "_chat", None)
        self._patch_require_chat(monkeypatch, pool)

        entry = await pool.get("mysession")
        entry._chat.messages = ["seeded"]
        entry._chat.history = FakeHistoryStore([{"role": "user", "content": "seeded"}])

        resp = await sessions_router.switch_session(SimpleNamespace(), SimpleNamespace(session_id="mysession"))

        assert resp.session_id == "mysession"
        assert resp.messages == 1
        assert pool.active == "mysession"
        assert state_mod._chat is pool._entries["mysession"]
        assert pool._entries["mysession"]._chat.session_id == "mysession"
        assert pool._entries["mysession"]._chat.messages == [{"role": "user", "content": "seeded"}]

    async def test_delete_session_router_evicts_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vajra_gate.routers.sessions as sessions_router
        import vajra_gate.state as state_mod

        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        monkeypatch.setattr(state_mod, "_pool", pool)
        monkeypatch.setattr(state_mod, "_chat", None)
        self._patch_require_chat(monkeypatch, pool)

        entry = await pool.get("doomed")
        entry._chat.history = FakeHistoryStore()

        resp = await sessions_router.delete_session(SimpleNamespace(), SimpleNamespace(session_id="doomed"))

        assert resp.deleted == "doomed"
        assert "doomed" not in pool._entries


class TestRequireChatResolution:
    async def test_require_chat_resolves_session_entries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import vajra_gate.chat as chat_mod
        import vajra_gate.state as state_mod

        builder = FakeBuilder()
        pool = ChatPool(builder=builder)
        monkeypatch.setattr(state_mod, "_pool", pool)
        monkeypatch.setattr(state_mod, "_chat", None)

        async def fake_init():
            state_mod._chat = await pool.get(pool.active)
            return state_mod._chat

        monkeypatch.setattr(chat_mod, "_init_chat", fake_init)

        a = await chat_mod._require_chat(SimpleNamespace(), session_id="session_a")
        b = await chat_mod._require_chat(SimpleNamespace(), session_id="session_b")

        assert a._chat is not b._chat
        assert a._chat.session_id == "session_a"
        assert b._chat.session_id == "session_b"

        active = await chat_mod._require_chat(SimpleNamespace())
        assert active is pool._entries[pool.active]
