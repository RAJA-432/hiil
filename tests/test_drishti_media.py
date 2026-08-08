from __future__ import annotations

import json
from pathlib import Path

import pytest

import drishti_engine.tools.media as media


@pytest.fixture
def no_dns(monkeypatch):
    """Skip DNS lookups for the fixed public hosts used by the media tools."""
    monkeypatch.setattr(media, "validate_public_http_url", lambda url: url)


class _FakeResponse:
    def __init__(self, payload=None, content=b"fake-png", error=None):
        self._payload = payload
        self._content = content
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload

    @property
    def content(self):
        return self._content


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        return self._response


def _set_httpx(monkeypatch, response=None, *, fail=False):
    if fail:

        def factory(**kwargs):
            raise media.httpx.ConnectError("network down")

        monkeypatch.setattr(media.httpx, "AsyncClient", factory)
    else:
        monkeypatch.setattr(media.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(response))


async def test_graphic_art_network_failure_writes_svg_fallback(tmp_path, monkeypatch, no_dns):
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    _set_httpx(monkeypatch, fail=True)
    result = json.loads(await media.graphic_art("a sunset over mountains"))
    assert result["provider"] == "local-fallback"
    out_path = Path(result["file"])
    assert out_path.parent == tmp_path
    assert out_path.exists()
    assert out_path.read_bytes().startswith(b"<svg")


async def test_graphic_art_success_saves_png(tmp_path, monkeypatch, no_dns):
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    _set_httpx(monkeypatch, response=_FakeResponse(content=b"real-png-bytes"))
    result = json.loads(await media.graphic_art("a mountain scene"))
    assert result["provider"] == "pollinations"
    assert Path(result["file"]).read_bytes() == b"real-png-bytes"


async def test_graphic_art_requires_prompt(tmp_path, monkeypatch, no_dns):
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    with pytest.raises(ValueError, match="prompt must not be empty"):
        await media.graphic_art("   ")


async def test_template_images_fallback_uses_local_catalog(monkeypatch, no_dns):
    monkeypatch.setattr(media, "PEXELS_API_KEY", "")
    _set_httpx(monkeypatch, fail=True)
    result = json.loads(await media.search_template_images("mountain"))
    assert result["provider"] == "local-fallback"
    assert result["count"] >= 1
    assert all("mountain" in r["title"].lower() or "mountain" in " ".join(r["tags"]).lower() for r in result["results"])


async def test_template_images_via_openverse(monkeypatch, no_dns):
    monkeypatch.setattr(media, "PEXELS_API_KEY", "")
    payload = {"results": [{"title": "Team meeting", "url": "https://cdn.example/1.jpg", "width": 100, "height": 50}]}
    _set_httpx(monkeypatch, response=_FakeResponse(payload=payload))
    result = json.loads(await media.search_template_images("meeting"))
    assert result["provider"] == "openverse"
    assert result["count"] == 1
    assert result["results"][0]["source"] == "openverse"


async def test_template_videos_local_catalog_without_key(monkeypatch, no_dns):
    monkeypatch.setattr(media, "PEXELS_API_KEY", "")
    result = json.loads(await media.search_template_videos("drone"))
    assert result["provider"] == "local-catalog"
    assert result["count"] >= 1


async def test_template_videos_via_pexels(monkeypatch, no_dns):
    monkeypatch.setattr(media, "PEXELS_API_KEY", "secret-key")
    payload = {"videos": [{"url": "https://cdn.example/v.mp4", "duration": 12}]}
    _set_httpx(monkeypatch, response=_FakeResponse(payload=payload))
    result = json.loads(await media.search_template_videos("product"))
    assert result["provider"] == "pexels"
    assert result["count"] == 1
    assert result["results"][0]["source"] == "pexels"
