from __future__ import annotations

import json
import logging
import logging.handlers
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_LOG_DIR = Path.home() / ".hiil"


class AuditJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        out = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("method", "path", "status", "duration_ms", "client", "user",
                     "resource", "action", "request_id", "error"):
            val = getattr(record, key, None)
            if val is not None:
                out[key] = val
        if record.exc_info and record.exc_info[0]:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def _setup_logger(name: str, filename: str, log_json: bool, log_level: str) -> logging.Logger:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _LOG_DIR / filename

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = AuditJsonFormatter() if log_json else logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        str(log_path), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(fmt if log_json else logging.Formatter(
        "[%(levelname)s] %(message)s",
    ))
    logger.addHandler(console_handler)

    return logger


def setup_vajra_gate_logger(log_json: bool = False, log_level: str = "INFO") -> None:
    _setup_logger("vajram", "vajram.log", log_json, log_level)


def setup_audit_logger(log_json: bool = False) -> logging.Logger:
    return _setup_logger("audit", "audit.log", log_json, "INFO")


_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _extract_resource(path: str, method: str) -> str:
    parts = path.strip("/").split("/")
    if not parts:
        return "root"
    if parts[0] == "api" and len(parts) > 1:
        return parts[1]
    return parts[0]


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("vajram.access")
        self.audit_logger = setup_audit_logger()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            dt_ms = (time.monotonic() - t0) * 1000
            status = 500
            error_detail = str(exc)
            self._record(request, request_id, dt_ms, status, error_detail)
            raise
        else:
            dt_ms = (time.monotonic() - t0) * 1000
            status = response.status_code
            self._record(request, request_id, dt_ms, status, None)
            return response

    def _record(
        self,
        request: Request,
        request_id: str,
        dt_ms: float,
        status: int,
        error_detail: str | None,
    ) -> None:
        client = request.client.host if request.client else "-"
        user = getattr(request.state, "user", None) or "-"
        path = request.url.path
        method = request.method
        resource = _extract_resource(path, method)

        extra = {
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(dt_ms, 1),
            "client": client,
            "user": user,
            "request_id": request_id,
            "resource": resource,
            "action": f"{method} {resource}",
        }
        if error_detail:
            extra["error"] = error_detail

        from vajra_gate.metrics import inc_request
        inc_request(method, path, status)

        self.logger.info(f"{method} {path} {status} ({dt_ms:.0f}ms)", extra=extra)

        if method in _MUTATING_METHODS or status >= 400:
            self.audit_logger.info(
                f"audit {method} {path} {status} user={user}",
                extra=extra,
            )
