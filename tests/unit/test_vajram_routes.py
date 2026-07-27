from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_chat():
    chat = MagicMock()
    chat.send = AsyncMock(return_value="Hello response")
    chat.claude.list_models = AsyncMock(return_value=["model1", "model2"])
    chat.claude.model = "model1"
    chat.get_status.return_value = {
        "session": "default", "messages": 5, "provider": "ollama",
        "model": "gemma4", "tools": 3, "servers": ["fs"],
    }
    chat.history.async_list_sessions = AsyncMock(return_value=["sess1", "sess2"])
    chat.history.async_load_session = AsyncMock(return_value=[
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ])
    chat.history.async_rename_session = AsyncMock(return_value=True)
    chat.history.async_delete_session = AsyncMock()
    chat.new_session.return_value = "session_abc"
    chat.session_id = "default"
    chat.messages = []
    chat.usage.session_summary.return_value = {"total_tokens": 100}
    chat.usage.total_summary.return_value = {"total_tokens": 500}
    chat.tools_by_name = {"tool1": MagicMock(), "tool2": MagicMock()}
    chat.call_tool_by_name = AsyncMock(return_value="tool result")
    chat.spawn_agent = MagicMock()
    chat.list_agents = MagicMock(return_value=["agent1"])
    chat.get_agent = MagicMock(return_value=None)
    chat.stop_agent = AsyncMock(return_value=True)
    chat.rag = MagicMock()
    chat.rag.index_document = AsyncMock(return_value={"indexed": 1, "total_chunks": 1})
    chat.rag.retrieve = AsyncMock(return_value=[])
    return chat


@pytest.fixture
def app(mock_chat):
    with (
        patch("vajra_gate.routers.knowledge._require_chat", new_callable=AsyncMock) as mock_req,
        patch("vajra_gate.routers.knowledge.storage"),
        patch("vajra_gate.routers.chat._require_chat", new_callable=AsyncMock) as mock_req2,
        patch("vajra_gate.routers.sessions._require_chat", new_callable=AsyncMock) as mock_req3,
        patch("vajra_gate.routers.agents._require_chat", new_callable=AsyncMock) as mock_req4,
    ):
        mock_req.return_value = mock_chat
        mock_req2.return_value = mock_chat
        mock_req3.return_value = mock_chat
        mock_req4.return_value = mock_chat
        from vajra_gate.auth import get_current_user
        from vajra_gate.routers import (
            agents_router,
            auth_router,
            chat_router,
            knowledge_router,
            misc_router,
            sessions_router,
        )

        application = FastAPI()
        application.include_router(auth_router)
        application.include_router(chat_router)
        application.include_router(sessions_router)
        application.include_router(knowledge_router)
        application.include_router(agents_router)
        application.include_router(misc_router)
        application.dependency_overrides[get_current_user] = lambda: "testuser"
        yield application, mock_chat, mock_req


@pytest.fixture
def client(app):
    application, _, _ = app
    return TestClient(application)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.2.0"
    assert isinstance(data["uptime_secs"], (float, int))
    assert isinstance(data["chat_initialized"], bool)


def test_hi(client):
    resp = client.get("/hi")
    assert resp.status_code == 200
    assert resp.text == '"hi"'


def test_root_redirect(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 308)
    assert resp.headers["location"] == "/canvas/"


def test_chat_api_non_streaming(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert data["reply"] == "Hello response"


def test_chat_api_empty_message(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_chat_api_streaming_response(app, client):
    _, mock_chat, _ = app
    with patch("vajra_gate.routers.chat._stream_chat") as mock_stream:
        mock_stream.return_value = iter([b'{"type":"tokens"}\n'])
        resp = client.post(
            "/api/chat?stream=1",
            json={"message": "hello"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")


def test_chat_api_streaming_via_accept_header(app, client):
    _, mock_chat, _ = app
    with patch("vajra_gate.routers.chat._stream_chat") as mock_stream:
        mock_stream.return_value = iter([b'{"type":"tokens"}\n'])
        resp = client.post(
            "/api/chat",
            json={"message": "hello"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")


def test_list_models(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "active" in data
    assert data["active"] == "model1"


def test_list_models_error(app, client):
    _, mock_chat, _ = app
    mock_chat.claude.list_models = AsyncMock(side_effect=RuntimeError("API down"))
    resp = client.get("/api/models")
    assert resp.status_code == 502


def test_get_status(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session"] == "default"


def test_set_model(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/model", json={"model": "gpt-4"})
    assert resp.status_code == 200
    assert resp.json()["model"] == "gpt-4"


def test_set_model_empty(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/model", json={"model": ""})
    assert resp.status_code == 400


def test_list_sessions(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessions"] == ["sess1", "sess2"]
    assert data["active"] == "default"


def test_get_history(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/history/sess1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["messages"]) == 2


def test_new_session(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/session/new")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "session_abc"


def test_switch_session(app, client):
    _, mock_chat, _ = app
    mock_chat.history.async_load_session = AsyncMock(return_value=[{"role": "user", "content": "test"}])
    resp = client.post("/api/session/switch", json={"session_id": "sess2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess2"
    assert data["messages"] == 1


def test_switch_session_empty(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/session/switch", json={"session_id": ""})
    assert resp.status_code == 400


def test_rename_session(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/session/rename", json={"old_id": "old", "new_id": "new"})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "new"


def test_rename_session_missing_params(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/session/rename", json={"old_id": ""})
    assert resp.status_code == 400


def test_rename_session_not_found(app, client):
    _, mock_chat, _ = app
    mock_chat.history.async_rename_session = AsyncMock(return_value=False)
    resp = client.post("/api/session/rename", json={"old_id": "ghost", "new_id": "new"})
    assert resp.status_code == 404


def test_delete_session(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/session/delete", json={"session_id": "sess1"})
    assert resp.status_code == 200
    assert resp.json()["deleted"] == "sess1"


def test_delete_session_empty(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/session/delete", json={"session_id": ""})
    assert resp.status_code == 400


def test_get_usage(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "session" in data
    assert "total" in data


def test_list_tools(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tool1" in data["tools"]
    assert "tool2" in data["tools"]


def test_call_tool(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/tools/call", json={"name": "my_tool", "arguments": {"x": 1}})
    assert resp.status_code == 200
    assert resp.json()["result"] == "tool result"


def test_call_tool_not_found(app, client):
    _, mock_chat, _ = app
    mock_chat.call_tool_by_name = AsyncMock(side_effect=ValueError("unknown tool"))
    resp = client.post("/api/tools/call", json={"name": "ghost"})
    assert resp.status_code == 404


def test_call_tool_bad_request(app, client):
    _, mock_chat, _ = app
    mock_chat.call_tool_by_name = AsyncMock(side_effect=RuntimeError("bad call"))
    resp = client.post("/api/tools/call", json={"name": "failing"})
    assert resp.status_code == 400


def test_upload_file(app, client):
    with patch("vajra_gate.routers.knowledge.storage.store_file", new_callable=AsyncMock, return_value="test-doc-id"):
        resp = client.post("/api/upload", files={"file": ("test.txt", b"hello world")})
    assert resp.status_code == 200
    data = resp.json()
    assert "doc_id" in data
    assert data["filename"] == "test.txt"


def test_upload_file_storage_error(app, client):
    _, _, mock_req = app
    with patch("vajra_gate.routers.knowledge.storage.store_file", new_callable=AsyncMock) as mock_store:
        mock_store.side_effect = RuntimeError("disk full")
        resp = client.post("/api/upload", files={"file": ("f.txt", b"data")})
        assert resp.status_code == 500


def test_list_documents(client):
    resp = client.get("/api/documents")
    assert resp.status_code == 200


def test_get_document_not_found(app, client):
    _, _, mock_req = app
    with patch("vajra_gate.routers.knowledge.storage.get_document") as mock_get:
        mock_get.side_effect = ValueError("not found")
        resp = client.get("/api/documents/nonexistent")
        assert resp.status_code == 404


def test_get_document(app, client):
    _, _, mock_req = app
    with (
        patch("vajra_gate.routers.knowledge.storage.get_document", return_value="content"),
        patch("vajra_gate.routers.knowledge.storage.get_file_content", new_callable=AsyncMock, return_value=b"file data"),
    ):
        resp = client.get("/api/documents/doc1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_id"] == "doc1"
        assert data["has_file"] is True


def test_create_agent(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    runner.agent_id = "agent_1"
    runner.config.name = "test_agent"
    runner.config.role = "helper"
    runner.config.capabilities = ["search"]
    runner.state.status = "idle"
    mock_chat.spawn_agent.return_value = runner

    resp = client.post("/api/agents", json={
        "name": "test_agent", "role": "helper", "capabilities": ["search"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == "agent_1"
    assert data["status"] == "idle"


def test_list_agents(app, client):
    _, mock_chat, _ = app
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    assert resp.json()["agents"] == ["agent1"]


def test_get_agent_not_found(app, client):
    _, mock_chat, _ = app
    mock_chat.get_agent.return_value = None
    resp = client.get("/api/agents/ghost")
    assert resp.status_code == 404


def test_get_agent_found(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    runner.agent_id = "agent_1"
    runner.config.model_dump.return_value = {"name": "test"}
    runner.state.model_dump.return_value = {"status": "idle"}
    runner.virtual_files = {}
    mock_chat.get_agent.return_value = runner

    resp = client.get("/api/agents/agent_1")
    assert resp.status_code == 200
    assert resp.json()["agent_id"] == "agent_1"


def test_add_agent_route(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/route", json={
        "virtual_prefix": "/docs",
        "real_path": "/var/docs",
    })
    assert resp.status_code == 200
    runner.add_route.assert_called_once_with("/docs", "/var/docs")


def test_add_agent_route_missing_params(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/route", json={"virtual_prefix": ""})
    assert resp.status_code == 400


def test_run_agent(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    runner.run = AsyncMock()
    runner.run.return_value = MagicMock()
    runner.run.return_value.model_dump.return_value = {"output": "done"}
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/run", json={"input": "do stuff"})
    assert resp.status_code == 200


def test_run_agent_empty_input(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/run", json={"input": ""})
    assert resp.status_code == 400


def test_run_agent_not_found(app, client):
    _, mock_chat, _ = app
    mock_chat.get_agent.return_value = None

    resp = client.post("/api/agents/ghost/run", json={"input": "test"})
    assert resp.status_code == 404


def test_resume_agent(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    runner.state.status = "waiting"
    runner.resume = AsyncMock()
    runner.resume.return_value = MagicMock()
    runner.resume.return_value.model_dump.return_value = {"output": "resumed"}
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/resume", json={
        "decisions": [{"type": "approve", "interrupt_id": "int_1"}],
    })
    assert resp.status_code == 200


def test_resume_agent_not_waiting(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    runner.state.status = "running"
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/resume", json={
        "decisions": [{"type": "approve", "interrupt_id": "int_1"}],
    })
    assert resp.status_code == 400


def test_resume_agent_no_decisions(app, client):
    _, mock_chat, _ = app
    runner = MagicMock()
    runner.state.status = "waiting"
    mock_chat.get_agent.return_value = runner

    resp = client.post("/api/agents/agent_1/resume", json={"decisions": []})
    assert resp.status_code == 400


def test_resume_agent_not_found(app, client):
    _, mock_chat, _ = app
    mock_chat.get_agent.return_value = None

    resp = client.post("/api/agents/ghost/resume", json={
        "decisions": [{"type": "approve", "interrupt_id": "int_1"}],
    })
    assert resp.status_code == 404


def test_stop_agent(app, client):
    _, mock_chat, _ = app
    resp = client.post("/api/agents/agent_1/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


def test_stop_agent_not_found(app, client):
    _, mock_chat, _ = app
    mock_chat.stop_agent = AsyncMock(return_value=False)
    resp = client.post("/api/agents/ghost/stop")
    assert resp.status_code == 404
