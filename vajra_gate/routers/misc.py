import os
import time

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

import vajra_gate.state as _state
from vajra_gate.config import WORKSPACE_DIR

_START_TIME = time.time()

router = APIRouter()


@router.get("/hi")
async def hi():
    return "hi"


@router.get("/health")
async def health():
    uptime_secs = time.time() - _START_TIME
    return {
        "status": "ok",
        "version": "0.2.0",
        "uptime_secs": round(uptime_secs, 1),
        "chat_initialized": _state._chat is not None,
    }


@router.get("/api/workspace")
async def workspace():
    return {
        "name": os.path.basename(WORKSPACE_DIR),
        "root": WORKSPACE_DIR,
    }


@router.get("/")
async def root():
    return RedirectResponse(url="/canvas/")
