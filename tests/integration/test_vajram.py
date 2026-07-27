from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_chat():
    chat = MagicMock()

    async def mock_send(user_input, **kwargs):
        bus = kwargs.get("notification_bus")
        on_chunk = kwargs.get("on_chunk")
        if bus:
            await bus.push_log("info", "Processing your request...")
            await bus.push_log("info", "Calling LLM (iteration 1)...")
        if on_chunk:
            on_chunk("Hello! ")
            on_chunk("How can I help?")
        if bus:
            await bus.push_log("debug", "Tokens: 100 in / 10 out")
            await bus.push_log("info", "Response complete.")
            await bus.push_done()
        return "Hello! How can I help?"

    chat.send = AsyncMock(side_effect=mock_send)
    chat.new_session = MagicMock(return_value="session_20260723_123456")
    chat.get_status = MagicMock(
        return_value={
            "session": "default",
            "messages": 10,
            "servers": ["filesystem", "memory"],
            "model": "gemma4:31b-cloud",
            "provider": "ollama",
            "tools": 12,
        }
    )
    chat.session_id = "default"
    chat.messages = []
    chat.history = MagicMock()
    chat.history.async_list_sessions = AsyncMock(return_value=["default", "test"])
    chat.history.async_load_session = AsyncMock(
        return_value=[{"role": "user", "content": "hi"}]
    )
    chat.claude = MagicMock()
    chat.claude.model = "gemma4:31b-cloud"
    chat.claude.list_models = AsyncMock(
        return_value=[{"id": "gemma4:31b-cloud"}, {"id": "llama3"}]
    )
    chat.tools_by_name = {"echo": {}, "grep": {}}
    chat.call_tool_by_name = AsyncMock(return_value="Echo: hi")
    chat.clients = {"filesystem": MagicMock(), "memory": MagicMock()}
    return chat


@pytest.fixture
def app(mock_chat):
    from mcp_cli.services.users import register_user
    from vajra_gate.auth import create_access_token

    register_user("testuser", "testpass")
    token = create_access_token("testuser")
    with patch("vajra_gate.chat._init_chat", AsyncMock(return_value=mock_chat)):
        from vajra_gate import app as _app
        with TestClient(_app) as client:
            client.headers["Authorization"] = f"Bearer {token}"
            yield client


class TestVajram:
    def test_root_redirect(self, app):
        resp = app.get("/", follow_redirects=False)
        assert resp.status_code in (307, 308)
        assert resp.headers["location"] == "/canvas/"

    def test_get_status(self, app):
        resp = app.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"] == "default"
        assert data["model"] == "gemma4:31b-cloud"
        assert data["provider"] == "ollama"

    def test_post_chat_non_streaming(self, app):
        resp = app.post("/api/chat", json={"message": "hello", "session_id": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert len(data["reply"]) > 0

    def test_post_chat_streaming(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "hello"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]

        types = {e["type"] for e in events}
        assert "log" in types
        assert "tokens" in types
        assert "done" in types

    def test_post_chat_empty_message(self, app):
        resp = app.post("/api/chat", json={"message": "", "session_id": "test"})
        assert resp.status_code == 400

    def test_list_models(self, app):
        resp = app.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "active" in data
        assert len(data["models"]) == 2

    def test_list_sessions(self, app):
        resp = app.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert data["active"] == "default"
        assert "default" in data["sessions"]

    def test_new_session(self, app):
        resp = app.post("/api/session/new")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"].startswith("session_")

    def test_get_history(self, app):
        resp = app.get("/api/history/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert len(data["messages"]) == 1

    def test_switch_session(self, app):
        resp = app.post("/api/session/switch", json={"session_id": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test"

    def test_switch_session_missing_id(self, app):
        resp = app.post("/api/session/switch", json={})
        assert resp.status_code == 400

    def test_list_tools(self, app):
        resp = app.get("/api/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "echo" in data["tools"]

    def test_call_tool(self, app):
        resp = app.post(
            "/api/tools/call",
            json={"name": "echo", "arguments": {"message": "hi"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "Echo: hi"

    def test_call_tool_not_found(self, app, mock_chat):
        mock_chat.call_tool_by_name = AsyncMock(return_value="Unknown tool: nonexistent")
        resp = app.post(
            "/api/tools/call",
            json={"name": "nonexistent", "arguments": {}},
        )
        assert resp.status_code == 200
        assert "Unknown tool" in resp.json()["result"]

    def test_set_model(self, app, mock_chat):
        resp = app.post("/api/model", json={"model": "llama3"})
        assert resp.status_code == 200
        assert resp.json()["model"] == "llama3"
        assert mock_chat.claude.model == "llama3"

    def test_set_model_missing(self, app):
        resp = app.post("/api/model", json={})
        assert resp.status_code == 400

    def test_proxy_root(self, app):
        resp = app.get("/")
        assert resp.status_code in (200, 502)

    def test_sse_log_events(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "test"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        log_events = [e for e in events if e["type"] == "log"]
        assert len(log_events) > 0
        assert any("Processing" in e["text"] for e in log_events)

    def test_sse_done_event(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "test"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        assert events[-1]["type"] == "done"

    def test_sse_tokens_yielded(self, app):
        resp = app.post(
            "/api/chat?stream=1",
            json={"message": "test"},
            headers={"Accept": "text/event-stream"},
        )
        lines = resp.text.strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        token_events = [e for e in events if e["type"] == "tokens"]
        assert len(token_events) > 0
        full = "".join(e["text"] for e in token_events)
        assert len(full) > 0

    @pytest.mark.asyncio
    async def test_notification_bus_log_progress_tool_events(self):
        from mcp_cli.services.notification_bus import NotificationBus

        bus = NotificationBus()
        sent_events: list[dict[str, Any]] = []

        async def capture():
            async for ev in bus.events():
                sent_events.append(ev)

        async def producer():
            await bus.push_log("info", "test log")
            await bus.push_progress(5, 10, "halfway")
            await bus.push_tool_call("echo", {"msg": "hi"}, "running")
            await bus.push_tokens("response text")
            await bus.push_done()

        import asyncio
        task = asyncio.create_task(capture())
        await asyncio.sleep(0)
        await producer()
        await asyncio.sleep(0.05)

        types = [e["type"] for e in sent_events]
        assert "log" in types
        assert "progress" in types
        assert "tool_event" in types
        assert "tokens" in types
        assert "done" in types
        assert sent_events[-1]["type"] == "done"
