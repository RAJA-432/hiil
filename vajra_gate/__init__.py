import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import vajra_gate.state as _state  # noqa: F401 -- imported for side effects (init state)
from vajra_gate.config import VAJRA_GATE_LOG_JSON, VAJRA_GATE_LOG_LEVEL
from vajra_gate.middleware.logging_middleware import AccessLogMiddleware, setup_vajra_gate_logger
from vajra_gate.middleware.rate_limit import RateLimitMiddleware
from vajra_gate.routers import (
    agents_router,
    auth_router,
    chat_router,
    files_router,
    knowledge_router,
    langgraph_router,
    misc_router,
    phase_c_router,
    rewards_router,
    search_router,
    sessions_router,
    skills_router,
)

setup_vajra_gate_logger(log_json=VAJRA_GATE_LOG_JSON, log_level=VAJRA_GATE_LOG_LEVEL)
logger = logging.getLogger("vajra_gate")

_WARMUP_TIMEOUT = float(os.getenv("VAJRA_GATE_PREWARM_TIMEOUT", "15"))
_WARMUP_DELAY = float(os.getenv("VAJRA_GATE_PREWARM_DELAY", "0.5"))
_PREWARM_DISABLED = os.getenv("VAJRA_GATE_DISABLE_PREWARM", "0") == "1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    prewarm_task: asyncio.Task[None] | None = None
    if not _PREWARM_DISABLED:
        _state._prewarm_task = _state._PREWARM_PENDING = None

        async def warmup_chat() -> None:
            await asyncio.sleep(_WARMUP_DELAY)
            try:
                await asyncio.wait_for(_state._get_pool().init(), timeout=_WARMUP_TIMEOUT)
            except (TimeoutError, asyncio.CancelledError, Exception) as exc:
                if not isinstance(exc, asyncio.CancelledError):
                    logger.warning("Prewarm failed: %s", exc)

        prewarm_task = asyncio.create_task(warmup_chat(), name="vajra_gate_prewarm")
        _state._prewarm_task = prewarm_task

    try:
        yield
    finally:
        if prewarm_task is not None and not prewarm_task.done():
            prewarm_task.cancel()
            try:
                await prewarm_task
            except (asyncio.CancelledError, Exception):
                pass
        _state._prewarm_task = None
        stack = getattr(_state, "_chat_stack", None)
        if stack is not None:
            try:
                await stack.aclose()
            except BaseExceptionGroup:
                pass
            except Exception:
                logger.exception("Chat stack cleanup error")
            _state._chat_stack = None
            _state._chat = None



app = FastAPI(title="H.I.I.L. — Hyper-Integrated Inference Engine API", version="0.2.0", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,testclient").split(","))

app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(langgraph_router)
app.include_router(phase_c_router)
app.include_router(rewards_router)
app.include_router(search_router)
app.include_router(sessions_router)
app.include_router(skills_router)
app.include_router(files_router)
app.include_router(misc_router)


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/canvas/assets/") and "immutable" not in response.headers.get("Cache-Control", ""):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

app.add_middleware(CacheControlMiddleware)

CANVAS_DIST = os.path.join(os.path.dirname(__file__), "..", "canvas_app", "frontend", "dist")
if os.path.isdir(CANVAS_DIST):
    app.mount("/canvas", StaticFiles(directory=CANVAS_DIST, html=True), name="canvas")
    logger.info("Serving canvas frontend from %s", CANVAS_DIST)
else:
    logger.warning("Canvas frontend dist not found at %s — build it with `cd canvas_app/frontend && npm run build`", CANVAS_DIST)
