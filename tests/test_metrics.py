from __future__ import annotations

from collections import defaultdict

import pytest

import vajra_gate.metrics as metrics_module


@pytest.fixture
def metrics_state(monkeypatch):
    monkeypatch.setattr(metrics_module, "_paths", set())
    monkeypatch.setattr(metrics_module, "_counts", defaultdict(int))
    monkeypatch.setattr(metrics_module, "_MAX_PATHS", 5)
    monkeypatch.setattr(metrics_module, "_chat_total", 0)
    monkeypatch.setattr(metrics_module, "_agent_runs", 0)
    monkeypatch.setattr(metrics_module, "_validation_errors_total", 0)
    yield


def test_path_cap_aggregates_to_other(metrics_state):
    for i in range(20):
        metrics_module.inc_request("GET", f"/api/{i}", 200)
    out = metrics_module.generate()
    assert "hiil_http_requests_total" in out
    assert 'path="/api/0"' in out
    assert 'path="/api/5"' not in out
    assert 'path="other"' in out
    assert len(metrics_module._paths) == 5


def test_other_aggregates_repeated_overflow(metrics_state):
    for i in range(5):
        metrics_module.inc_request("GET", f"/api/{i}", 200)
    for _ in range(3):
        metrics_module.inc_request("GET", "/overflow", 200)
    out = metrics_module.generate()
    assert 'hiil_http_requests_total{method="GET",path="other",status="200"} 3' in out


def test_overflow_paths_dont_grow_counters(metrics_state):
    for i in range(100):
        metrics_module.inc_request("GET", f"/api/{i}", 200)
    assert len(metrics_module._counts) <= 5 + 1


def test_generate_still_valid(metrics_state):
    metrics_module.inc_request("GET", "/health", 200)
    metrics_module.inc_request("POST", "/x", 500)
    out = metrics_module.generate()
    assert out.startswith("# HELP hiil_uptime_seconds")
    assert "hiil_uptime_seconds " in out
    assert "hiil_chat_messages_total 0" in out
    assert out.endswith("\n")
