from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@pytest.fixture
def app():
    from vajra_gate.__init__ import app as _app

    yield _app


def test_app_is_fastapi(app):
    assert isinstance(app, FastAPI)
    assert app.title == "hiil API Gateway"
    assert app.version == "0.2.0"


def test_cors_middleware_configured(app):
    middleware_types = [m.cls for m in app.user_middleware]
    assert CORSMiddleware in middleware_types


def test_cors_allows_origins(app):
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            assert "http://localhost:8000" in m.kwargs["allow_origins"]
            assert "http://127.0.0.1:8000" in m.kwargs["allow_origins"]


def test_cors_credentials_methods_headers(app):
    for m in app.user_middleware:
        if m.cls is CORSMiddleware:
            assert m.kwargs["allow_credentials"] is True
            assert m.kwargs["allow_methods"] == ["*"]
            assert m.kwargs["allow_headers"] == ["*"]


def test_routers_are_mounted(app):
    all_paths = set()
    for r in app.routes:
        if hasattr(r, "path") and r.path:
            all_paths.add(r.path)
        if hasattr(r, "original_router"):
            for sr in r.original_router.routes:
                if hasattr(sr, "path") and sr.path:
                    all_paths.add(sr.path)
    assert "/health" in all_paths
