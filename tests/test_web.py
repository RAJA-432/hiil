from __future__ import annotations

import socket

import pytest

import veda_engine.tools.web as web_module
from veda_engine.tools.web import _validate_url, web_fetch

PUBLIC_IP = "93.184.216.34"
PRIVATE_IP = "10.0.0.5"


def _fake_getaddrinfo(ip: str):
    def _fake(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _fake


@pytest.fixture
def no_real_dns(monkeypatch):
    monkeypatch.setattr(web_module.socket, "getaddrinfo", _fake_getaddrinfo(PUBLIC_IP))


class FakeStream:
    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    async def aiter_bytes(self):
        for chunk in self.chunks:
            yield chunk


class _StreamCM:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *exc):
        return False


class _Client:
    def __init__(self, response, **kwargs):
        self.response = response

    def stream(self, *args, **kwargs):
        return _StreamCM(self.response)


class _AsyncClient:
    def __init__(self, response, **kwargs):
        self.response = response

    async def __aenter__(self):
        return _Client(self.response)

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_httpx(monkeypatch):
    def _install(chunks, error=None):
        monkeypatch.setattr(
            web_module.httpx, "AsyncClient", lambda **kw: _AsyncClient(FakeStream(chunks, error))
        )

    return _install


def test_validate_url_rejects_private_resolution(monkeypatch):
    monkeypatch.setattr(web_module.socket, "getaddrinfo", _fake_getaddrinfo(PRIVATE_IP))
    with pytest.raises(ValueError, match="private/reserved"):
        _validate_url("http://evil.example.com/page")


def test_validate_url_accepts_public_resolution(monkeypatch):
    monkeypatch.setattr(web_module.socket, "getaddrinfo", _fake_getaddrinfo(PUBLIC_IP))
    assert _validate_url("http://example.com/page") == "http://example.com/page"


@pytest.mark.parametrize("url", [
    "http://localhost/x",
    "http://foo.internal/x",
    "ftp://example.com/x",
])
def test_validate_url_string_level_rejections(url):
    with pytest.raises(ValueError):
        _validate_url(url)


def test_validate_url_rejects_literal_private_ip():
    with pytest.raises(ValueError, match="private/reserved"):
        _validate_url("http://10.0.0.5/x")


def test_validate_url_unresolvable_host(monkeypatch):
    def _fail(host, *args, **kwargs):
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(web_module.socket, "getaddrinfo", _fail)
    with pytest.raises(ValueError, match="Could not resolve"):
        _validate_url("http://does-not-exist.example/x")


async def test_web_fetch_happy_path(fake_httpx, no_real_dns):
    fake_httpx([b"<html><body><p>Hello <b>world</b></p><script>var x = 1;</script></body></html>"])
    out = await web_fetch("http://example.com/", max_chars=8000)
    assert out == "Hello world"


async def test_web_fetch_body_cap_truncates(fake_httpx, no_real_dns, monkeypatch):
    monkeypatch.setattr(web_module, "_MAX_RESPONSE_BYTES", 150)
    fake_httpx([b"a" * 100, b"b" * 100, b"c" * 100])
    out = await web_fetch("http://example.com/", max_chars=50000)
    assert f"[truncated at {web_module._MAX_RESPONSE_BYTES} bytes]" in out
    assert "a" * 100 in out
    assert "b" * 100 in out
    assert "c" * 100 not in out


async def test_web_fetch_max_chars_truncation(fake_httpx, no_real_dns):
    fake_httpx([b"<p>" + b"x" * 2000 + b"</p>"])
    out = await web_fetch("http://example.com/", max_chars=500)
    assert out == "x" * 500 + "..."
