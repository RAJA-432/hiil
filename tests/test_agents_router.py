from __future__ import annotations

from types import SimpleNamespace

from tests.gate_helpers import FakeChat, make_client
from vajra_gate.routers.agents import router as agents_router


def _config(name: str = "researcher", role: str = "research", capabilities: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, role=role, capabilities=list(capabilities or []))


class TestAgentsRouter:
    def test_create_agent(self):
        chat = FakeChat()
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post("/api/agents", json={"name": "researcher", "role": "research", "capabilities": ["web"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "researcher"
        assert data["role"] == "research"
        assert data["capabilities"] == ["web"]
        assert data["status"] == "idle"
        assert "agent_" in data["agent_id"]

    def test_create_agent_rejects_missing_required_fields(self):
        chat = FakeChat()
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post("/api/agents", json={"name": "researcher"})

        assert resp.status_code == 422

    def test_list_agents(self):
        chat = FakeChat()
        chat.spawn_agent(_config(capabilities=["web"]))
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.get("/api/agents")

        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert len(agents) == 1
        assert agents[0]["name"] == "researcher"
        assert agents[0]["status"] == "idle"

    def test_get_agent(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config(capabilities=["web"]))
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.get(f"/api/agents/{runner.agent_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == runner.agent_id
        assert data["config"]["name"] == "researcher"
        assert data["state"]["status"] == "idle"

    def test_get_agent_404(self):
        chat = FakeChat()
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.get("/api/agents/does_not_exist")

        assert resp.status_code == 404

    def test_add_agent_route(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(
                f"/api/agents/{runner.agent_id}/route",
                json={"virtual_prefix": "/res", "real_path": "/data/research"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "status": "route_added",
            "virtual_prefix": "/res",
            "real_path": "/data/research",
        }
        assert runner.added_routes == [("/res", "/data/research")]

    def test_add_agent_route_missing_path_400(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(
                f"/api/agents/{runner.agent_id}/route",
                json={"virtual_prefix": "/res", "real_path": ""},
            )

        assert resp.status_code == 400

    def test_run_agent(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(f"/api/agents/{runner.agent_id}/run", json={"input": "summarize the paper"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["output"] == "agent result"
        assert runner.run_input == "summarize the paper"

    def test_run_agent_requires_input(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(f"/api/agents/{runner.agent_id}/run", json={"input": "   "})

        assert resp.status_code == 400

    def test_resume_agent(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        runner._status = "waiting"
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(
                f"/api/agents/{runner.agent_id}/resume",
                json={"decisions": [{"type": "approve"}]},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert len(runner.resume_decisions) == 1

    def test_resume_agent_not_waiting_400(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(
                f"/api/agents/{runner.agent_id}/resume",
                json={"decisions": [{"type": "approve"}]},
            )

        assert resp.status_code == 400

    def test_stop_agent(self):
        chat = FakeChat()
        runner = chat.spawn_agent(_config())
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post(f"/api/agents/{runner.agent_id}/stop")

        assert resp.status_code == 200
        assert resp.json() == {"status": "stopped"}
        assert runner.stopped is True

    def test_stop_agent_404(self):
        chat = FakeChat()
        with make_client(agents_router, patch_target="vajra_gate.routers.agents._require_chat", chat=chat) as client:
            resp = client.post("/api/agents/does_not_exist/stop")

        assert resp.status_code == 404
