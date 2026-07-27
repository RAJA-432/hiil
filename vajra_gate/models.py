from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class KaryaRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}
