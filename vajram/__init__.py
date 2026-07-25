import logging
import subprocess

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import vajram.state as _state
from vajram.config import STREAMLIT_URL, VAJRAM_LOG_LEVEL, VAJRAM_NO_STREAMLIT
from vajram.streamlit import _start_streamlit

logging.basicConfig(level=VAJRAM_LOG_LEVEL)
logger = logging.getLogger("vajram")

_chat_process: subprocess.Popen | None = None


async def lifespan(app: FastAPI):
    global _chat_process

    app.state.streamlit_url = STREAMLIT_URL
    app.state.http_client = httpx.AsyncClient(timeout=300)

    if not VAJRAM_NO_STREAMLIT:
        _chat_process = _start_streamlit()
    yield
    await app.state.http_client.aclose()
    if _state._chat is not None:
        try:
            await _state._chat.close()
        except Exception:
            pass
    if _state._chat_stack is not None:
        try:
            await _state._chat_stack.aclose()
        except Exception:
            pass
        _state._chat_stack = None
    if _chat_process is not None:
        _chat_process.terminate()
        try:
            _chat_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _chat_process.kill()


app = FastAPI(title="hiil API Gateway", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from vajram.proxy import router as proxy_router
from vajram.routes import router as api_router

app.include_router(api_router)
app.include_router(proxy_router)
