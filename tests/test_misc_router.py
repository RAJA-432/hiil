from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vajra_gate.routers.misc import router as misc_router


class TestMiscHealth:
    def _client(self) -> TestClient:
        app = FastAPI()
        app.include_router(misc_router)
        return TestClient(app)

    def test_hi(self):
        with self._client() as client:
            resp = client.get("/hi")
        assert resp.status_code == 200
        assert resp.json() == "hi"

    def test_health(self):
        with self._client() as client:
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.2.0"
        assert "uptime_secs" in data
        assert "chat_initialized" in data
