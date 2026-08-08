from __future__ import annotations

import asyncio
import importlib
import json
import sys

import pytest

import mcp_cli.services.error_reporting as error_reporting
from mcp_cli.services.error_reporting import (
    METRICS_ENDPOINT_ENV,
    SENTRY_DSN_ENV,
    SERVICE_NAME,
    arecord_metric,
    capture_exception,
    capture_message,
    init_sentry,
    is_enabled,
    record_metric,
    record_token_status,
)


@pytest.fixture(autouse=True)
def _isolated_module(monkeypatch):
    monkeypatch.setattr(error_reporting, "_SENTRY_INITIALIZED", False)
    monkeypatch.setattr(error_reporting, "_SENTRY_MODULE", None)
    monkeypatch.setattr(error_reporting, "_SENTRY_UNAVAILABLE", False)
    monkeypatch.delenv(SENTRY_DSN_ENV, raising=False)
    monkeypatch.delenv(METRICS_ENDPOINT_ENV, raising=False)


def test_is_enabled_false_without_dsn():
    assert is_enabled() is False


def test_init_sentry_false_when_disabled():
    assert init_sentry() is False
    assert error_reporting._SENTRY_INITIALIZED is False


def test_capture_and_metrics_never_raise_when_disabled():
    capture_exception(RuntimeError("boom"))
    capture_exception(RuntimeError("boom"), extra={"ctx": "x"})
    capture_message("hello")
    capture_message("hello", level="error", extra={"a": 1})
    record_metric("x", 1)
    record_metric("x", 1, {"a": "b"})


class FakeClient:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, headers=None):
        self.calls.append({"url": url, "data": data, "headers": headers})


def test_record_metric_pushes_json_to_fake_client(monkeypatch):
    monkeypatch.setenv(METRICS_ENDPOINT_ENV, "http://fake/metrics")
    fake = FakeClient()
    record_metric("x", 1, {"a": "b"}, client=fake)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "http://fake/metrics"
    body = json.loads(call["data"])
    assert body["service"] == SERVICE_NAME
    assert body["metric"] == "x"
    assert body["value"] == 1
    assert body["tags"] == {"a": "b"}
    assert isinstance(body["ts"], float)


class FakeAsyncClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, data=None, headers=None):
        self.calls.append({"url": url, "data": data, "headers": headers})


def test_arecord_metric_uses_fake_async_client(monkeypatch):
    monkeypatch.setenv(METRICS_ENDPOINT_ENV, "http://fake/metrics")
    fake = FakeAsyncClient()
    asyncio.run(arecord_metric("y", 2.5, client=fake))

    assert len(fake.calls) == 1
    body = json.loads(fake.calls[0]["data"])
    assert body["metric"] == "y"
    assert body["value"] == 2.5


def test_record_token_status_warn_hooks(monkeypatch):
    recorded = {"messages": [], "metrics": []}

    def fake_capture_message(msg, level="warning", extra=None):
        recorded["messages"].append((msg, level, extra))

    def fake_record_metric(name, value, tags=None, client=None):
        recorded["metrics"].append((name, value))

    monkeypatch.setattr(error_reporting, "capture_message", fake_capture_message)
    monkeypatch.setattr(error_reporting, "record_metric", fake_record_metric)

    record_token_status({"level": "warn", "total_tokens": 3600, "session_id": "s"})

    assert recorded["messages"] == [
        ("token usage warn: 3600", "warning", {"level": "warn", "total_tokens": 3600, "session_id": "s"})
    ]
    assert recorded["metrics"] == [("token.total", 3600)]


def test_record_token_status_critical_uses_error_level(monkeypatch):
    recorded = {"messages": [], "metrics": []}
    monkeypatch.setattr(
        error_reporting,
        "capture_message",
        lambda msg, level="warning", extra=None: recorded["messages"].append((msg, level, extra)),
    )
    monkeypatch.setattr(
        error_reporting,
        "record_metric",
        lambda name, value, tags=None, client=None: recorded["metrics"].append((name, value)),
    )

    record_token_status({"level": "critical", "total_tokens": 3900})

    assert recorded["messages"] == [("token usage critical: 3900", "error", {"level": "critical", "total_tokens": 3900})]
    assert recorded["metrics"] == [("token.total", 3900)]


def test_record_token_status_ignores_ok_and_missing_tokens(monkeypatch):
    recorded = {"messages": [], "metrics": []}
    monkeypatch.setattr(
        error_reporting,
        "capture_message",
        lambda msg, level="warning", extra=None: recorded["messages"].append((msg, level, extra)),
    )
    monkeypatch.setattr(
        error_reporting,
        "record_metric",
        lambda name, value, tags=None, client=None: recorded["metrics"].append((name, value)),
    )

    record_token_status({"level": "ok", "total_tokens": 100})
    record_token_status({"level": "warn"})

    assert recorded["messages"] == [("token usage warn: 0", "warning", {"level": "warn"})]
    assert recorded["metrics"] == [("token.total", 0)]


def test_import_is_hermetic_with_dsn_set_and_sentry_absent(monkeypatch):
    monkeypatch.setenv(SENTRY_DSN_ENV, "https://fake@sentry.invalid/1")
    monkeypatch.delitem(sys.modules, "mcp_cli.services.error_reporting", raising=False)
    module = importlib.import_module("mcp_cli.services.error_reporting")
    assert module is not error_reporting
    assert module.is_enabled() is False
    assert module.init_sentry() is False
