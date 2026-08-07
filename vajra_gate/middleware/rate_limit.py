from __future__ import annotations

import logging
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from vajra_gate.auth import _decode_token
from vajra_gate.services.rate_limiter import RateLimiter

logger = logging.getLogger("vajra_gate.rate_limit")

_limiter = RateLimiter(default_rate=10.0, default_capacity=20)

_TRUSTED_PROXIES: frozenset[str] = frozenset(
    p.strip()
    for p in os.getenv("HIIL_TRUSTED_PROXIES", "").split(",")
    if p.strip()
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        key = _get_client_key(request)
        if not _limiter.check(key):
            return Response(
                status_code=429,
                content="Rate limit exceeded",
                headers={"Retry-After": "1"},
            )
        return await call_next(request)


def _get_client_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user}"

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        username = _decode_token(auth[7:].strip())
        if username:
            return f"user:{username}"

    # X-Forwarded-For is only trusted when the direct peer is a known proxy;
    # otherwise a client could spoof the header to rotate rate-limit buckets.
    if (
        _TRUSTED_PROXIES
        and request.client is not None
        and request.client.host in _TRUSTED_PROXIES
    ):
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

    client = request.client
    if client:
        return f"ip:{client.host}"
    return "unknown"
