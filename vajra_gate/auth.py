from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_SECRET: str = os.getenv("HIIL_JWT_SECRET") or ""
if not _SECRET:
    import hashlib
    _SECRET = hashlib.sha256(b"hiil-jwt-fallback-secret-do-not-use-in-production").hexdigest()
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

_bearer = HTTPBearer(auto_error=False)


def create_access_token(username: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": username,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def _decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    auth_header = request.headers.get("Authorization", "")
    token: str | None = None

    if credentials is not None:
        token = credentials.credentials
    elif auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if token is not None:
        username = _decode_token(token)
        if username is not None:
            return username
    return "default"
