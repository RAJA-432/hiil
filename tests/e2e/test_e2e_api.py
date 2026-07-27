from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mcp_cli.services.notification_bus import NotificationBus
from tests.harness import assert_api_response, load_cases


@pytest.fixture(autouse=True)
def auth_token():
    """Register a test user and return a Bearer token."""
    from mcp_cli.services.users import delete_user, register_user

    register_user("testuser", "testpass")
    from vajra_gate.auth import create_access_token

    yield create_access_token("testuser")
    delete_user("testuser")


@pytest.fixture
def app(auth_token):
    """Patch _init_chat to return a mock, then yield the real TestClient."""
    chat = MagicMock()
    chat.send = AsyncMock()

    async def mock_send(user_input, **kwargs):
        bus = kwargs.get("notification_bus")
        on_chunk = kwargs.get("on_chunk")
        if on_chunk:
            on_chunk("Hello from the AI! ")
            on_chunk("How can I help you today?")
        if bus:
            await bus.push_log("info", "Processing...")
            await bus.push_log("info", "Calling LLM (iteration 1)...")
            await bus.push_log("debug", "Tokens: 100 in / 10 out")
            await bus.push_log("info", "Response complete.")
            await bus.push_done()
        return "Hello from the AI! How can I help you today?"

    chat.send.side_effect = mock_send
    chat.get_status = MagicMock(return_value={
        "session": "default", "messages": 5, "servers": ["fs"],
        "model": "gemma4", "provider": "ollama", "tools": 3,
    })
    chat.session_id = "default"
    chat.messages = []
    chat.new_session = MagicMock(return_value="session_new_001")
    chat.history = MagicMock()
    chat.history.async_list_sessions = AsyncMock(return_value=["default"])
    chat.history.async_load_session = AsyncMock(
        return_value=[{"role": "user", "content": "hi"}]
    )
    chat.claude = MagicMock()
    chat.claude.model = "gemma4"
    chat.claude.list_models = AsyncMock(return_value=[
        {"id": "gemma4", "name": "Gemma 4"},
        {"id": "llama3", "name": "Llama 3"},
    ])
    chat.tools_by_name = {"read_file": MagicMock()}
    chat.call_tool_by_name = AsyncMock(return_value="Tool executed successfully")
    chat.call_tool_by_name.side_effect = (
        lambda name, args: "Tool executed successfully"
        if name == "read_file"
        else (_ for _ in ()).throw(ValueError(f"Tool '{name}' not found"))
    )

    with patch("vajra_gate.chat._init_chat", return_value=chat):
        from vajra_gate import app as fastapi_app
        with TestClient(fastapi_app) as client:
            client.headers["Authorization"] = f"Bearer {auth_token}"
            yield client


@pytest.fixture
def real_app(auth_token):
    """Build a real CliChat+Claude (mocked only at network boundary) and mount it.

    Exercises ``Claude.__init__``, ``CliChat.__init__``, history, context
    manager, and vector store. Only ``AsyncOpenAI`` and ``create_servers``
    are mocked — everything else is the real production code.
    """
    from unittest.mock import MagicMock, patch

    from mcp_cli.services.chat import CliChat
    from mcp_cli.services.claude import Claude

    with patch("mcp_cli.services.claude.AsyncOpenAI") as mock_oa:
        oa_client = MagicMock()
        oa_client.chat = MagicMock()
        oa_client.chat.completions = MagicMock()
        oa_client.chat.completions.create = AsyncMock()
        mock_oa.return_value = oa_client

        claude = Claude(provider="test", model="gpt-4o", api_key="", base_url="http://localhost:9999")
        chat = CliChat(doc_client=None, clients={}, claude_service=claude)
        with patch("vajra_gate.chat._init_chat", return_value=chat):
            from vajra_gate import app as fastapi_app
            with TestClient(fastapi_app) as client:
                client.headers["Authorization"] = f"Bearer {auth_token}"
                yield client


API_CASES = load_cases("api_e2e_tests.json")


class TestApiE2EDataDriven:
    @pytest.mark.parametrize("case", API_CASES, ids=lambda c: c["id"])
    def test_api(self, app, case):
        method = case["method"].lower()
        handler = getattr(app, method)
        json_body = case.get("json")
        headers = case.get("headers", {})
        if "json" in case:
            resp = handler(case["path"], json=json_body, headers=headers)
        else:
            resp = handler(case["path"], headers=headers)
        assert_api_response(case, resp)


class TestApiE2ESpecial:
    def test_streaming_chat_events(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "hello", "session_id": "default"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

        lines = resp.text.strip().split("\n")
        assert len(lines) > 0

        events = [json.loads(l) for l in lines if l.strip()]
        types = [e["type"] for e in events]

        assert "tokens" in types
        assert "log" in types
        assert "done" in types
        assert events[-1]["type"] == "done"

    def test_streaming_contains_tokens_before_done(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "hello", "session_id": "default"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        token_texts = [e["text"] for e in events if e["type"] == "tokens"]
        assert any(token_texts)
        assert events[-1]["type"] == "done"

    def test_notification_bus_multiple_subscribers(self):
        bus = NotificationBus()
        collected_a = []
        collected_b = []

        async def sub_a():
            async for ev in bus.events():
                collected_a.append(ev)

        async def sub_b():
            async for ev in bus.events():
                collected_b.append(ev)

        import asyncio

        async def run():
            task_a = asyncio.create_task(sub_a())
            task_b = asyncio.create_task(sub_b())
            await asyncio.sleep(0)
            await bus.push_log("info", "broadcast test")
            await bus.push_tokens("some tokens")
            await bus.push_done()
            await asyncio.sleep(0.05)
            return task_a, task_b

        task_a, task_b = asyncio.run(run())
        assert len(collected_a) == 3
        assert len(collected_b) == 3
        assert collected_a[-1]["type"] == "done"
        assert collected_b[-1]["type"] == "done"

    def test_streaming_events_have_expected_structure(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "hello", "session_id": "default"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        for ev in events:
            assert "type" in ev
        token_events = [e for e in events if e["type"] == "tokens"]
        assert all("text" in e for e in token_events)
        log_events = [e for e in events if e["type"] == "log"]
        assert all("level" in e and "text" in e for e in log_events)

    def test_multiple_chat_turns(self, app):
        for i in range(3):
            resp = app.post(
                "/api/chat",
                json={"message": f"turn {i + 1}", "session_id": "default"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "reply" in data
            assert len(data["reply"]) > 0

    def test_switch_session_then_chat(self, app):
        resp = app.post("/api/session/switch", json={"session_id": "default"})
        assert resp.status_code == 200
        resp = app.post(
            "/api/chat",
            json={"message": "after switch", "session_id": "default"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data

    def test_streaming_events_ordered(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "hello", "session_id": "default"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        assert events[-1]["type"] == "done"
        log_before_done = [e for e in events[:-1] if e["type"] == "log"]
        assert len(log_before_done) > 0

    def test_notification_bus_subscriber_exception_isolation(self):
        bus = NotificationBus()
        good_events = []

        async def failing_sub():
            async for ev in bus.events():
                raise RuntimeError("subscriber failed")

        async def good_sub():
            async for ev in bus.events():
                good_events.append(ev)

        import asyncio

        async def run():
            task_fail = asyncio.create_task(failing_sub())
            task_good = asyncio.create_task(good_sub())
            await asyncio.sleep(0)
            await bus.push_log("info", "test")
            await bus.push_done()
            await asyncio.sleep(0.05)
            task_fail.cancel()
            task_good.cancel()
            return task_good

        asyncio.run(run())
        assert len(good_events) == 2

    def test_notification_bus_push_done_idempotent(self):
        bus = NotificationBus()
        collected = []

        async def sub():
            async for ev in bus.events():
                collected.append(ev)

        import asyncio

        async def run():
            task = asyncio.create_task(sub())
            await asyncio.sleep(0)
            await bus.push_log("info", "first")
            await bus.push_done()
            await bus.push_done()
            await bus.push_done()
            await asyncio.sleep(0.05)
            task.cancel()

        asyncio.run(run())
        assert len(collected) == 2
        assert collected[-1]["type"] == "done"

    def test_tool_call_endpoint_success(self, app):
        resp = app.post(
            "/api/tools/call",
            json={"name": "read_file", "arguments": {"path": "test.txt"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data

    def test_tool_call_endpoint_not_found(self, app):
        resp = app.post(
            "/api/tools/call",
            json={"name": "ghost_tool", "arguments": {}},
        )
        assert resp.status_code == 404

    # --- Tests with real CliChat (mocked only at network boundary) ---

    def test_real_app_health(self, real_app):
        resp = real_app.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.2.0"
        assert isinstance(data["uptime_secs"], (float, int))
        assert isinstance(data["chat_initialized"], bool)

    def test_real_app_status(self, real_app):
        resp = real_app.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"] == "default"
        assert data["provider"] == "test"
        assert data["model"] == "gpt-4o"

    def test_real_app_new_session(self, real_app):
        resp = real_app.post("/api/session/new")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"].startswith("session_")

    def test_real_app_sessions(self, real_app):
        resp = real_app.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "active" in data


# --- RAG E2E tests ---


@pytest.fixture
def rag_app(auth_token):
    """Real CliChat+Claude with mocked embed (returns fixed vector).

    Exercises the full RAG pipeline (chunker, vector store, RagPipeline)
    without needing a real embedding provider. ``AsyncOpenAI`` and
    ``Claude.embed`` are mocked; everything else is real.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from mcp_cli.services.chat import CliChat
    from mcp_cli.services.claude import Claude

    with (
        patch("mcp_cli.services.claude.AsyncOpenAI") as mock_oa,
        patch.object(Claude, "embed", new_callable=AsyncMock) as mock_embed,
    ):
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        oa_client = MagicMock()
        oa_client.chat = MagicMock()
        oa_client.chat.completions = MagicMock()
        oa_client.chat.completions.create = AsyncMock()
        mock_oa.return_value = oa_client

        claude = Claude(
            provider="test", model="gpt-4o", api_key="",
            base_url="http://localhost:9999",
        )
        chat = CliChat(doc_client=None, clients={}, claude_service=claude)
        with patch("vajra_gate.chat._init_chat", return_value=chat):
            from vajra_gate import app as fastapi_app
            with TestClient(fastapi_app) as client:
                client.headers["Authorization"] = f"Bearer {auth_token}"
                yield client


class TestRagE2E:
    """End-to-end tests for the RAG knowledge base pipeline."""

    def test_upload_indexes_document(self, rag_app):
        resp = rag_app.post(
            "/api/upload",
            files={"file": ("hello.txt", b"Hello world from the knowledge base")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "doc_id" in data
        assert data["filename"] == "hello.txt"
        assert "rag" in data
        assert data["rag"]["indexed"] >= 1
        assert data["rag"]["total_chunks"] >= 1

    def test_knowledge_lists_indexed_documents(self, rag_app):
        rag_app.post(
            "/api/upload",
            files={"file": ("doc_a.txt", b"Content of document A for testing")},
        )
        rag_app.post(
            "/api/upload",
            files={"file": ("doc_b.txt", b"Content of document B for testing")},
        )
        resp = rag_app.get("/api/knowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        filenames = [d["filename"] for d in data["documents"]]
        assert "doc_a.txt" in filenames
        assert "doc_b.txt" in filenames
        for d in data["documents"]:
            assert d["chunks"] >= 1

    def test_retrieve_returns_results_with_expected_structure(self, rag_app):
        rag_app.post(
            "/api/upload",
            files={"file": ("colors.txt", b"Red green blue yellow purple orange")},
        )
        resp = rag_app.post(
            "/api/retrieve",
            json={"query": "colors", "top_k": 5, "min_score": 0.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        for r in data["results"]:
            assert "text" in r
            assert "score" in r
            assert "metadata" in r
            assert isinstance(r["score"], float)
            assert 0.0 <= r["score"] <= 1.0

    def test_retrieve_with_high_min_score_excludes(self, rag_app):
        rag_app.post(
            "/api/upload",
            files={"file": ("data.txt", b"Some test content for similarity search")},
        )
        resp = rag_app.post(
            "/api/retrieve",
            json={"query": "test content", "top_k": 5, "min_score": 1.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_retrieve_empty_query_returns_400(self, rag_app):
        resp = rag_app.post("/api/retrieve", json={"query": ""})
        assert resp.status_code == 400

    def test_streaming_chat_emits_rag_context_event(self, rag_app):
        rag_app.post(
            "/api/upload",
            files={"file": ("kb.txt", b"Important knowledge for the AI assistant")},
        )
        resp = rag_app.post(
            "/api/chat?stream=1",
            json={"message": "tell me about the knowledge base"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        types = [e["type"] for e in events]
        assert "rag_context" in types

    def test_rag_context_has_expected_structure(self, rag_app):
        rag_app.post(
            "/api/upload",
            files={"file": ("data.txt", b"Content for RAG context structure test")},
        )
        resp = rag_app.post(
            "/api/chat?stream=1",
            json={"message": "query about data"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        rag_events = [e for e in events if e["type"] == "rag_context"]
        assert len(rag_events) >= 1
        for ev in rag_events:
            chunks = ev.get("chunks", [])
            assert isinstance(chunks, list)
            for c in chunks:
                assert "text" in c
                assert "score" in c
                assert "metadata" in c
                assert "filename" in c["metadata"]

    def test_upload_multiple_files_increases_count(self, rag_app):
        n = 5
        for i in range(n):
            rag_app.post(
                "/api/upload",
                files={"file": (f"multi_{i}.txt", f"Content of document number {i}".encode())},
            )
        resp = rag_app.get("/api/knowledge")
        assert resp.status_code == 200
        data = resp.json()
        filenames = [d["filename"] for d in data["documents"]]
        for i in range(n):
            assert f"multi_{i}.txt" in filenames

    def test_upload_large_text_chunks_correctly(self, rag_app):
        words = ["word"] * 2000
        text = " ".join(words)
        resp = rag_app.post(
            "/api/upload",
            files={"file": ("large.txt", text.encode())},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rag"]["total_chunks"] > 1
        assert data["rag"]["indexed"] == data["rag"]["total_chunks"]
