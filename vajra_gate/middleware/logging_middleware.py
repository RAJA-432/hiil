from __future__ import annotations

import logging
import logging.handlers
import time
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

_LOG_DIR = Path.home() / ".hiil"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        out = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("method", "path", "status", "duration_ms", "client", "user"):
            val = getattr(record, key, None)
            if val is not None:
                out[key] = val
        if record.exc_info and record.exc_info[0]:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_vajra_gate_logger(log_json: bool = False, log_level: str = "INFO") -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _LOG_DIR / "vajram.log"

    logger = logging.getLogger("vajram")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = JsonFormatter() if log_json else logging.Formatter(
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


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("vajram.access")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        t0 = time.monotonic()
        response = await call_next(request)
        dt_ms = (time.monotonic() - t0) * 1000

        extra = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(dt_ms, 1),
            "client": request.client.host if request.client else "-",
        }
        user = getattr(request.state, "user", None)
        if user:
            extra["user"] = user

        self.logger.info(
            f"{request.method} {request.url.path} {response.status_code} ({dt_ms:.0f}ms)",
            extra=extra,
        )
        return response
