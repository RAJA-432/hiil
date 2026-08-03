from __future__ import annotations

import time

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
