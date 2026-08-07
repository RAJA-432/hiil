from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from vajra_gate.middleware.security import DEFAULT_CSP, SecurityHeadersMiddleware


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/ok")
    def ok():
        return {"status": "ok"}

    @app.get("/stream")
    def stream():
        async def gen():
            yield b"chunk1"
            yield b"chunk2"

        return StreamingResponse(gen(), media_type="text/event-stream")

    app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(app)


class TestSecurityHeaders:
    def test_plain_response_has_all_security_headers(self):
        with _client() as client:
            resp = client.get("/ok")
        assert resp.status_code == 200
        headers = resp.headers
        assert headers["content-security-policy"] == DEFAULT_CSP
        assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert headers["x-frame-options"] == "SAMEORIGIN"
        assert headers["cross-origin-opener-policy"] == "same-origin"
        assert headers["cross-origin-resource-policy"] == "same-origin"

    def test_streaming_response_has_all_security_headers(self):
        with _client() as client:
            resp = client.get("/stream")
        assert resp.status_code == 200
        assert resp.content == b"chunk1chunk2"
        headers = resp.headers
        assert headers["content-security-policy"] == DEFAULT_CSP
        assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert headers["x-frame-options"] == "SAMEORIGIN"
        assert headers["cross-origin-opener-policy"] == "same-origin"
        assert headers["cross-origin-resource-policy"] == "same-origin"

    def test_csp_directives_are_restrictive(self):
        csp = DEFAULT_CSP
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "frame-ancestors 'self'" in csp
        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
