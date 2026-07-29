import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vajra_gate.config import VAJRA_GATE_LOG_JSON, VAJRA_GATE_LOG_LEVEL
from vajra_gate.middleware.logging_middleware import AccessLogMiddleware, setup_vajra_gate_logger

setup_vajra_gate_logger(log_json=VAJRA_GATE_LOG_JSON, log_level=VAJRA_GATE_LOG_LEVEL)
logger = logging.getLogger("vajra_gate")

import vajra_gate.state as _state  # noqa: F401 -- imported for side effects (init state)
from vajra_gate.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
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



app = FastAPI(title="hiil API Gateway", version="0.2.0", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RateLimitMiddleware)

from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,testclient").split(","))

from vajra_gate.routers import (
    agents_router,
    auth_router,
    chat_router,
    files_router,
    knowledge_router,
    langgraph_router,
    misc_router,
    phase_c_router,
    sessions_router,
    skills_router,
)

app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(langgraph_router)
app.include_router(phase_c_router)
app.include_router(sessions_router)
app.include_router(skills_router)
app.include_router(files_router)
app.include_router(misc_router)

CANVAS_DIST = os.path.join(os.path.dirname(__file__), "..", "canvas_app", "frontend", "dist")
if os.path.isdir(CANVAS_DIST):
    app.mount("/canvas", StaticFiles(directory=CANVAS_DIST, html=True), name="canvas")
    logger.info("Serving canvas frontend from %s", CANVAS_DIST)
else:
    logger.warning("Canvas frontend dist not found at %s — build it with `cd canvas_app/frontend && npm run build`", CANVAS_DIST)
