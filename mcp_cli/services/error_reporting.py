from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

SENTRY_DSN_ENV = "HIIL_SENTRY_DSN"
METRICS_ENDPOINT_ENV = "HIIL_METRICS_ENDPOINT"
SERVICE_NAME = "hiil"

_TRACES_SAMPLE_RATE = 0.1
_METRICS_HEADERS = {"Content-Type": "application/json"}

_SENTRY_INITIALIZED = False
_SENTRY_MODULE: Any | None = None
_SENTRY_UNAVAILABLE = False


def _log() -> logging.Logger:
    return logging.getLogger("hiil")


def _sentry() -> Any | None:
    global _SENTRY_MODULE, _SENTRY_UNAVAILABLE
    if _SENTRY_UNAVAILABLE:
        return None
    if _SENTRY_MODULE is None:
        try:
            import sentry_sdk
        except ImportError:
            _SENTRY_UNAVAILABLE = True
            return None
        _SENTRY_MODULE = sentry_sdk
    return _SENTRY_MODULE


def _active_sentry() -> Any | None:
    if not _SENTRY_INITIALIZED:
        return None
    return _sentry()


def is_enabled() -> bool:
    """True only when HIIL_SENTRY_DSN is set and sentry_sdk is importable."""
    if not os.getenv(SENTRY_DSN_ENV):
        return False
    return _sentry() is not None


def init_sentry(dsn: str | None = None) -> bool:
    """Initialise Sentry once; no-op when not configured or sentry_sdk is missing."""
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return True
    if dsn is None and not is_enabled():
        return False
    dsn = dsn or os.getenv(SENTRY_DSN_ENV)
    if not dsn:
        return False
    sdk = _sentry()
    if sdk is None:
        return False
    try:
        sdk.init(dsn=dsn, traces_sample_rate=_TRACES_SAMPLE_RATE)
        sdk.set_tag("service", SERVICE_NAME)
    except Exception:
        return False
    _SENTRY_INITIALIZED = True
    return True


def capture_exception(exc: BaseException, extra: dict | None = None) -> None:
    """Report an exception to Sentry, or log a warning when Sentry is inactive."""
    sdk = _active_sentry()
    if sdk is not None:
        try:
            if extra:
                sdk.set_context("extra", extra)
            sdk.capture_exception(exc)
        except Exception:
            pass
        return
    _log().warning("capture_exception skipped (sentry inactive): %r", exc)


def capture_message(msg: str, level: str = "warning", extra: dict | None = None) -> None:
    """Report a message to Sentry, or log a warning when Sentry is inactive."""
    sdk = _active_sentry()
    if sdk is not None:
        try:
            if extra:
                sdk.set_context("extra", extra)
            sdk.capture_message(msg, level=level)
        except Exception:
            pass
        return
    _log().warning("capture_message skipped (sentry inactive): %s", msg)


def record_metric(
    name: str,
    value: float | int,
    tags: dict | None = None,
    client: Any | None = None,
) -> None:
    """Push a Grafana-style JSON metric when HIIL_METRICS_ENDPOINT is configured."""
    if not os.getenv(METRICS_ENDPOINT_ENV):
        _log().debug("metric %s skipped (no endpoint configured)", name)
        return
    try:
        _emit(name, value, tags, client)
    except Exception:
        _log().warning("metric %s failed to push", name, exc_info=True)


async def arecord_metric(
    name: str,
    value: float | int,
    tags: dict | None = None,
    client: Any | None = None,
) -> None:
    """Async variant of ``record_metric``; never raises."""
    if not os.getenv(METRICS_ENDPOINT_ENV):
        _log().debug("metric %s skipped (no endpoint configured)", name)
        return
    try:
        await _aemit(name, value, tags, client)
    except Exception:
        _log().warning("metric %s failed to push", name, exc_info=True)


def record_token_status(status: dict) -> None:
    """Report token usage warn/critical levels via capture/message and metric hooks."""
    level = status.get("level")
    if level not in ("warn", "critical"):
        return
    total = status.get("total_tokens", 0)
    if not isinstance(total, (int, float)):
        total = 0
    capture_message(
        f"token usage {level}: {total}",
        level="error" if level == "critical" else "warning",
        extra=status,
    )
    record_metric("token.total", total)


def _payload(name: str, value: float | int, tags: dict | None) -> str:
    return json.dumps(
        {
            "service": SERVICE_NAME,
            "metric": name,
            "value": value,
            "tags": tags or {},
            "ts": time.time(),
        }
    )


def _emit(name: str, value: float | int, tags: dict | None, client: Any | None) -> None:
    endpoint = os.getenv(METRICS_ENDPOINT_ENV)
    if not endpoint:
        return
    data = _payload(name, value, tags)
    if client is not None:
        client.post(endpoint, data=data, headers=_METRICS_HEADERS)
        return
    try:
        import httpx
    except ImportError:
        _log().warning("httpx unavailable; metric %s not pushed", name)
        return
    httpx.post(endpoint, data=data, headers=_METRICS_HEADERS)


async def _aemit(
    name: str,
    value: float | int,
    tags: dict | None,
    client: Any | None,
) -> None:
    endpoint = os.getenv(METRICS_ENDPOINT_ENV)
    if not endpoint:
        return
    data = _payload(name, value, tags)
    if client is not None:
        await client.post(endpoint, data=data, headers=_METRICS_HEADERS)
        return
    try:
        import httpx
    except ImportError:
        _log().warning("httpx unavailable; metric %s not pushed", name)
        return
    async with httpx.AsyncClient() as http:
        await http.post(endpoint, data=data, headers=_METRICS_HEADERS)
