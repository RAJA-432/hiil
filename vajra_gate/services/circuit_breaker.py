from __future__ import annotations

import threading
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
            return self._state

    def call(self, fn):
        with self._lock:
            if self._state == CircuitState.OPEN:
                raise RuntimeError(f"Circuit breaker '{self.name}' is OPEN")
        try:
            result = fn()
            self._success()
            return result
        except Exception as exc:
            self._failure()
            raise

    async def acall(self, fn):
        with self._lock:
            if self._state == CircuitState.OPEN:
                raise RuntimeError(f"Circuit breaker '{self.name}' is OPEN")
        try:
            result = await fn()
            self._success()
            return result
        except Exception as exc:
            self._failure()
            raise

    def _success(self):
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def _failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    def reset(self):
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
