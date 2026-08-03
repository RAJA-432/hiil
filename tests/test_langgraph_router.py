from __future__ import annotations

from tests.gate_helpers import FakeChat, FakeStore, make_client
from vajra_gate.routers.langgraph import router as langgraph_router


class TestLanggraphMisc:
    def test_ok(self):
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=FakeChat()) as client:
            resp = client.get("/ok")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_info(self):
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=FakeChat()) as client:
            resp = client.get("/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "hiil-gateway"
        assert data["langgraph_compat"] is True
        assert "/threads" in data["endpoints"]


class TestLanggraphThreads:
    def test_create_thread(self):
        chat = FakeChat()
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/threads", json={"metadata": {"note": "x"}})
        assert resp.status_code == 200
        assert resp.json()["thread_id"] == "session_20260803_120000"
        assert chat.session_id == "session_20260803_120000"

    def test_list_threads(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.get("/threads")
        assert resp.status_code == 200
        threads = resp.json()["threads"]
        assert len(threads) == 1
        assert threads[0]["thread_id"] == "session_1"
        assert threads[0]["message_count"] == 1

    def test_get_thread(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.get("/threads/session_1")
        assert resp.status_code == 200
        assert resp.json()["thread_id"] == "session_1"
        assert resp.json()["message_count"] == 1

    def test_get_thread_404(self):
        chat = FakeChat()
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.get("/threads/nope")
        assert resp.status_code == 404

    def test_run_thread(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/threads/session_1/runs", json={"input": {"messages": "hello world"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "session_1"
        assert data["status"] == "completed"
        assert data["output"] == {"reply": "reply:hello world"}
        assert chat.sent_inputs == ["hello world"]

    def test_run_thread_missing_input_400(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/threads/session_1/runs", json={"input": {}})
        assert resp.status_code == 400

    def test_run_thread_404(self):
        chat = FakeChat()
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/threads/nope/runs", json={"input": {"messages": "hi"}})
        assert resp.status_code == 404

    def test_run_thread_wait(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/threads/session_1/runs/wait", json={"input": {"messages": "hello"}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_stateless_run(self):
        chat = FakeChat()
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/runs", json={"input": {"messages": "ping"}})
        assert resp.status_code == 200
        assert resp.json()["output"] == {"reply": "reply:ping"}

    def test_stateless_run_restores_session(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        chat.session_id = "session_1"
        chat.messages = [{"role": "user", "content": "hi"}]
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/runs", json={"input": {"messages": "ping"}})
        assert resp.status_code == 200
        assert chat.session_id == "session_1"
        assert chat.messages == [{"role": "user", "content": "hi"}]

    def test_search_thread(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hello"}]})
        with make_client(langgraph_router, patch_target="vajra_gate.routers.langgraph._require_chat", chat=chat) as client:
            resp = client.post("/threads/session_1/search", json={"query": "anything", "top_k": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestLanggraphStore:
    def _make_store_client(self, store):
        return make_client(
            langgraph_router,
            patch_target="vajra_gate.routers.langgraph._require_chat",
            chat=FakeChat(),
            extra_patches=[("vajra_gate.routers.langgraph.get_store", store)],
        )

    def test_store_upsert(self):
        store = FakeStore()
        with self._make_store_client(store) as client:
            resp = client.put(
                "/store/items",
                json={"namespace": "ns", "items": [{"key": "k1", "value": {"a": 1}}]},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "namespace": "ns", "count": 1}
        assert store.get("ns", "k1")["value"] == {"a": 1}

    def test_store_get(self):
        store = FakeStore()
        store.upsert("ns", [{"key": "k1", "value": {"a": 1}}])
        with self._make_store_client(store) as client:
            resp = client.get("/store/items", params={"namespace": "ns", "keys": "k1"})
        assert resp.status_code == 200
        assert resp.json()["items"][0]["key"] == "k1"

    def test_store_get_requires_keys(self):
        with self._make_store_client(FakeStore()) as client:
            resp = client.get("/store/items", params={"namespace": "ns"})
        assert resp.status_code == 400

    def test_store_get_post(self):
        store = FakeStore()
        store.upsert("ns", [{"key": "k1", "value": {"a": 1}}])
        with self._make_store_client(store) as client:
            resp = client.post("/store/items/query", json={"namespace": "ns", "keys": ["k1"]})
        assert resp.status_code == 200
        assert resp.json()["items"][0]["key"] == "k1"

    def test_store_delete(self):
        store = FakeStore()
        store.upsert("ns", [{"key": "k1", "value": {"a": 1}}])
        with self._make_store_client(store) as client:
            resp = client.request("DELETE", "/store/items", json={"namespace": "ns", "keys": ["k1"]})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "deleted": 1, "namespace": "ns"}

    def test_store_search(self):
        store = FakeStore()
        store.upsert("ns", [{"key": "k1", "value": {"a": 1}}, {"key": "k2", "value": {"a": 2}}])
        with self._make_store_client(store) as client:
            resp = client.post("/store/items/search", json={"namespace": "ns", "filter": {"a": 1}, "limit": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        assert resp.json()["items"][0]["key"] == "k1"
