from __future__ import annotations

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from vajra_gate.services.rate_limiter import RateLimiter

_limiter = RateLimiter(default_rate=10.0, default_capacity=20)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        key = _get_client_key(request)
        if not _limiter.check(key):
            raise HTTPException(status_code=429, detail="Too many requests")
        return await call_next(request)


def _get_client_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user}"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client = request.client
    if client:
        return f"ip:{client.host}"
    return "unknown"
