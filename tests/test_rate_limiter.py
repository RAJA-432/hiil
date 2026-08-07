from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import vajra_gate.middleware.rate_limit as rate_limit_module
from vajra_gate.middleware.rate_limit import RateLimitMiddleware, _get_client_key
from vajra_gate.services.rate_limiter import RateLimiter


def test_prune_idle_removes_only_stale_buckets():
    limiter = RateLimiter()
    limiter.check("active")
    limiter.check("stale")
    limiter._last_used["stale"] = time.monotonic() - 10_000
    pruned = limiter.prune_idle(max_idle_seconds=3600.0)
    assert pruned == 1
    assert "stale" not in limiter._buckets
    assert "active" in limiter._buckets


def test_check_still_works_after_pruning():
    limiter = RateLimiter()
    limiter.check("a")
    limiter._last_used["a"] = time.monotonic() - 10_000
    limiter.prune_idle()
    assert "a" not in limiter._buckets
    assert limiter.check("a") is True
    assert "a" in limiter._buckets


def test_prune_leaves_recent_keys():
    limiter = RateLimiter()
    for i in range(10):
        limiter.check(f"key_{i}")
    limiter._last_used["key_0"] = time.monotonic() - 10_000
    limiter._last_used["key_1"] = time.monotonic() - 10_000
    pruned = limiter.prune_idle(max_idle_seconds=3600.0)
    assert pruned == 2
    assert "key_0" not in limiter._buckets
    assert "key_1" not in limiter._buckets
    assert "key_2" in limiter._buckets


def test_check_triggers_prune_periodically(monkeypatch):
    limiter = RateLimiter()
    pruned = [0]
    original = limiter.prune_idle

    def counting(*args, **kwargs):
        pruned[0] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(limiter, "prune_idle", counting)
    for i in range(97):
        limiter.check(f"key_{i}")
    assert pruned[0] >= 1


class _FakeState:
    user = None


def _make_request(headers=None, host: str = "9.9.9.9"):
    return SimpleNamespace(
        headers=dict(headers or {}),
        client=SimpleNamespace(host=host),
        state=_FakeState(),
    )


def test_middleware_returns_429_when_rate_limited(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "_limiter", RateLimiter(default_rate=0.0, default_capacity=1))
    app = FastAPI()

    @app.get("/x")
    async def x():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    with TestClient(app) as client:
        first = client.get("/x")
        second = client.get("/x")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("Retry-After") == "1"
    assert second.text == "Rate limit exceeded"


def test_client_key_uses_ip_when_forwarded_for_untrusted():
    req = _make_request(headers={"X-Forwarded-For": "1.2.3.4"}, host="9.9.9.9")
    assert _get_client_key(req) == "ip:9.9.9.9"


def test_client_key_trusts_forwarded_for_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "_TRUSTED_PROXIES", frozenset({"10.0.0.1"}))
    req = _make_request(headers={"X-Forwarded-For": "8.8.8.8"}, host="10.0.0.1")
    assert _get_client_key(req) == "ip:8.8.8.8"


def test_client_key_uses_bearer_token_username(monkeypatch):
    from vajra_gate.auth import create_access_token

    token = create_access_token("alice")
    req = _make_request(headers={"Authorization": f"Bearer {token}"}, host="9.9.9.9")
    assert _get_client_key(req) == "user:alice"
