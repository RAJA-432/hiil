from __future__ import annotations

import os

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob: http: https:; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self' https://cdn.jsdelivr.net; "
    "worker-src 'self' blob: https://cdn.jsdelivr.net; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'"
)

_SECURITY_HEADERS = {
    "Content-Security-Policy": os.getenv("HIIL_CSP", DEFAULT_CSP),
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class SecurityHeadersMiddleware:
    """Pure ASGI middleware injecting security headers on every HTTP response.

    Implemented as raw ASGI (not BaseHTTPMiddleware) so the headers also apply
    to streaming responses such as the SSE chat stream.
    """

    def __init__(self, app: ASGIApp, headers: dict[str, str] | None = None) -> None:
        self.app = app
        self.headers = headers or _SECURITY_HEADERS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
