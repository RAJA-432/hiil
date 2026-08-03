from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class RateLimiter:
    def __init__(self, default_rate: float = 10.0, default_capacity: int = 20):
        self._default_rate = default_rate
        self._default_capacity = default_capacity
        self._buckets: dict[str, TokenBucket] = {}
        self._last_used: dict[str, float] = {}
        self._lock = threading.Lock()

    def _bucket(self, key: str) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(self._default_rate, self._default_capacity)
            self._last_used[key] = time.monotonic()
            return self._buckets[key]

    def check(self, key: str, tokens: int = 1) -> bool:
        bucket = self._bucket(key)
        allowed = bucket.consume(tokens)
        if len(self._buckets) % 97 == 0:
            self.prune_idle()
        return allowed

    def configure(self, key: str, rate: float, capacity: int):
        with self._lock:
            self._buckets[key] = TokenBucket(rate, capacity)
            self._last_used[key] = time.monotonic()

    def prune_idle(self, max_idle_seconds: float = 3600.0) -> int:
        now = time.monotonic()
        with self._lock:
            stale = [
                key for key, last in self._last_used.items()
                if now - last > max_idle_seconds
            ]
            for key in stale:
                self._buckets.pop(key, None)
                self._last_used.pop(key, None)
        return len(stale)
