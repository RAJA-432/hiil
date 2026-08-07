from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from mcp_cli.services.usage import UsageTracker


class FakeUsage:
    def __init__(self):
        self.requested_session: str | None = None

    def session_summary(self):
        return {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3, "cost": 0.0001}

    async def async_session_summary_for(self, session_id: str):
        self.requested_session = session_id
        return {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "cost": 0.001}

    def total_summary(self):
        return {"input_tokens": 5, "output_tokens": 6, "total_tokens": 11, "cost": 0.0005}

    async def async_total_summary(self):
        return {"input_tokens": 5, "output_tokens": 6, "total_tokens": 11, "cost": 0.0005}


class FakeChat:
    def __init__(self):
        self.usage = FakeUsage()


def test_session_summary_for_aggregates_per_session(tmp_path):
    tracker = UsageTracker(str(tmp_path / "usage_test.db"))
    tracker.record("gpt-4o", 100, 50, session_id="session_a")
    tracker.record("gpt-4o", 200, 100, session_id="session_a")
    tracker.record("gpt-4o", 10, 5, session_id="session_b")

    summary_a = tracker.session_summary_for("session_a")
    assert summary_a["input_tokens"] == 300
    assert summary_a["output_tokens"] == 150
    assert summary_a["total_tokens"] == 450

    summary_b = tracker.session_summary_for("session_b")
    assert summary_b["input_tokens"] == 10
    assert summary_b["output_tokens"] == 5
    assert summary_b["total_tokens"] == 15

    total = tracker.total_summary()
    assert total["input_tokens"] == 310
    assert total["output_tokens"] == 155
    assert total["total_tokens"] == 465


def test_session_summary_for_unknown_session_returns_zeros(tmp_path):
    tracker = UsageTracker(str(tmp_path / "usage_test.db"))
    tracker.record("gpt-4o", 100, 50, session_id="session_a")
    assert tracker.session_summary_for("missing") == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }


async def test_async_session_summary_for(tmp_path):
    tracker = UsageTracker(str(tmp_path / "usage_test.db"))
    tracker.record("gpt-4o", 100, 50, session_id="session_a")
    summary = await tracker.async_session_summary_for("session_a")
    assert summary["input_tokens"] == 100
    assert summary["output_tokens"] == 50
    assert summary["total_tokens"] == 150


def test_usage_endpoint_returns_session_shape():
    from vajra_gate import app

    fake_chat = FakeChat()
    with patch("vajra_gate.routers.chat._require_chat", new=AsyncMock(return_value=fake_chat)):
        with TestClient(app) as client:
            resp = client.get("/api/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session"] == {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
        "cost": 0.0001,
    }
    assert data["total"] == {
        "input_tokens": 5,
        "output_tokens": 6,
        "total_tokens": 11,
        "cost": 0.0005,
    }


def test_usage_endpoint_session_id_routes_to_per_session():
    from vajra_gate import app

    fake_chat = FakeChat()
    with patch("vajra_gate.routers.chat._require_chat", new=AsyncMock(return_value=fake_chat)):
        with TestClient(app) as client:
            resp = client.get("/api/usage?session_id=session_x")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session"] == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "cost": 0.001,
    }
    assert data["total"] == {
        "input_tokens": 5,
        "output_tokens": 6,
        "total_tokens": 11,
        "cost": 0.0005,
    }
    assert fake_chat.usage.requested_session == "session_x"
