from __future__ import annotations

from types import SimpleNamespace

from tests.gate_helpers import FakeChat, FakeScheduler, make_client
from vajra_gate.routers.phase_c import router as phase_c_router


class TestPhaseCMetrics:
    def test_metrics_returns_prometheus_text(self):
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=FakeChat()) as client:
            resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "# HELP hiil_uptime_seconds" in resp.text
        assert "hiil_chat_messages_total" in resp.text


class TestPhaseCCrons:
    def test_create_cron(self):
        scheduler = FakeScheduler()
        with make_client(
            phase_c_router,
            patch_target="vajra_gate.routers.phase_c._require_chat",
            chat=FakeChat(),
            extra_patches=[("vajra_gate.routers.phase_c.get_scheduler", scheduler)],
        ) as client:
            resp = client.post("/crons", json={"task_input": "daily digest", "schedule_seconds": 60})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["cron"]["id"] == "cron_abc"
        assert data["cron"]["task_input"] == "daily digest"
        assert scheduler.started_with is not None

    def test_create_cron_requires_task_input(self):
        with make_client(
            phase_c_router,
            patch_target="vajra_gate.routers.phase_c._require_chat",
            chat=FakeChat(),
            extra_patches=[("vajra_gate.routers.phase_c.get_scheduler", FakeScheduler())],
        ) as client:
            resp = client.post("/crons", json={"task_input": "", "schedule_seconds": 60})

        assert resp.status_code == 400

    def test_create_cron_rejects_schedule_below_10(self):
        with make_client(
            phase_c_router,
            patch_target="vajra_gate.routers.phase_c._require_chat",
            chat=FakeChat(),
            extra_patches=[("vajra_gate.routers.phase_c.get_scheduler", FakeScheduler())],
        ) as client:
            resp = client.post("/crons", json={"task_input": "digest", "schedule_seconds": 5})

        assert resp.status_code == 400

    def test_list_crons(self):
        scheduler = FakeScheduler()
        scheduler.add(60, "digest")
        with make_client(
            phase_c_router,
            patch_target="vajra_gate.routers.phase_c._require_chat",
            chat=FakeChat(),
            extra_patches=[("vajra_gate.routers.phase_c.get_scheduler", scheduler)],
        ) as client:
            resp = client.get("/crons")

        assert resp.status_code == 200
        assert len(resp.json()["crons"]) == 1
        assert resp.json()["crons"][0]["id"] == "cron_abc"

    def test_get_cron_404(self):
        with make_client(
            phase_c_router,
            patch_target="vajra_gate.routers.phase_c._require_chat",
            chat=FakeChat(),
            extra_patches=[("vajra_gate.routers.phase_c.get_scheduler", FakeScheduler())],
        ) as client:
            resp = client.get("/crons/nope")

        assert resp.status_code == 404


class TestPhaseCMcpTools:
    def test_list_tools(self):
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=FakeChat()) as client:
            resp = client.get("/mcp/tools")

        assert resp.status_code == 200
        data = resp.json()
        assert data["transport"] == "rest"
        names = [t["name"] for t in data["tools"]]
        assert "hiil_chat" in names
        assert "hiil_run_agent" in names

    def test_call_hiil_chat(self):
        chat = FakeChat()
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=chat) as client:
            resp = client.post("/mcp/tools/hiil_chat", json={"message": "hello"})

        assert resp.status_code == 200
        assert resp.json() == {"result": "reply:hello", "tool": "hiil_chat"}
        assert chat.sent_inputs == ["hello"]

    def test_call_hiil_chat_requires_message(self):
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=FakeChat()) as client:
            resp = client.post("/mcp/tools/hiil_chat", json={"message": ""})

        assert resp.status_code == 400

    def test_call_hiil_list_threads(self):
        chat = FakeChat(sessions={"session_1": []})
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=chat) as client:
            resp = client.post("/mcp/tools/hiil_list_threads", json={})

        assert resp.status_code == 200
        assert resp.json() == {"result": {"threads": ["session_1"]}, "tool": "hiil_list_threads"}

    def test_call_hiil_get_thread(self):
        chat = FakeChat(sessions={"session_1": [{"role": "user", "content": "hi"}]})
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=chat) as client:
            resp = client.post("/mcp/tools/hiil_get_thread", json={"thread_id": "session_1"})

        assert resp.status_code == 200
        assert resp.json()["result"]["thread_id"] == "session_1"
        assert len(resp.json()["result"]["messages"]) == 1

    def test_call_hiil_get_thread_404(self):
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=FakeChat()) as client:
            resp = client.post("/mcp/tools/hiil_get_thread", json={"thread_id": "nope"})

        assert resp.status_code == 404

    def test_call_hiil_create_agent(self):
        chat = FakeChat()
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=chat) as client:
            resp = client.post("/mcp/tools/hiil_create_agent", json={"name": "researcher", "role": "research", "capabilities": ["web"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["tool"] == "hiil_create_agent"
        assert data["result"]["name"] == "researcher"
        assert data["result"]["status"] == "idle"
        assert "agent_" in data["result"]["agent_id"]

    def test_call_hiil_run_agent(self):
        chat = FakeChat()
        runner = chat.spawn_agent(SimpleNamespace(name="r", role="x", capabilities=[]))
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=chat) as client:
            resp = client.post("/mcp/tools/hiil_run_agent", json={"agent_id": runner.agent_id, "task": "do it"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["tool"] == "hiil_run_agent"
        assert data["result"]["status"] == "completed"
        assert data["result"]["output"] == "agent result"

    def test_call_hiil_run_agent_404(self):
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=FakeChat()) as client:
            resp = client.post("/mcp/tools/hiil_run_agent", json={"agent_id": "nope", "task": "do it"})

        assert resp.status_code == 404

    def test_call_unknown_tool_404(self):
        with make_client(phase_c_router, patch_target="vajra_gate.routers.phase_c._require_chat", chat=FakeChat()) as client:
            resp = client.post("/mcp/tools/hiil_bogus", json={})

        assert resp.status_code == 404
