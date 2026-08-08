"""MCP tools for image generation and stock-template search.

Image generation uses the keyless Pollinations.ai API with a local SVG fallback;
stock-template search queries Pexels (when an API key is configured) or the
keyless Openverse API, falling back to local catalog entries on any error.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote_plus

import httpx
from pydantic import Field

from drishti_engine.config import (
    GRAPHIC_ART_PROVIDER_URL,
    MEDIA_DIR,
    OPENVERSE_IMAGES_URL,
    PEXELS_API_KEY,
    PEXELS_IMAGES_URL,
    PEXELS_VIDEOS_URL,
)
from drishti_engine.data.media import FALLBACK_IMAGES, FALLBACK_VIDEOS
from drishti_engine.tools._net import validate_public_http_url

_TIMEOUT = 30
_MAX_BYTES = 4 * 1024 * 1024


def _slug(text: str) -> str:
    """Return a lowercase alphanumeric dash slug for ``text``, capped at ~60 chars."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")
    return slug or "image"


def _ensure_media_dir() -> Path:
    """Create and return the media output directory."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return MEDIA_DIR


async def _fetch_bytes(url: str) -> bytes:
    """Fetch ``url`` and return its raw bytes, capped at ``_MAX_BYTES``."""
    url = await asyncio.to_thread(validate_public_http_url, url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        body = resp.content
    if len(body) > _MAX_BYTES:
        raise ValueError(f"Response exceeds the {_MAX_BYTES} byte limit")
    return body


def _svg_placeholder(prompt: str, width: int, height: int) -> bytes:
    """Build a minimal SVG placeholder image (dashed border + prompt text) as bytes."""
    escaped = prompt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect x="8" y="8" width="{width - 16}" height="{height - 16}" fill="none" '
        f'stroke="#8892a0" stroke-width="3" stroke-dasharray="10 8" rx="12"/>'
        f'<text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="sans-serif" font-size="24" fill="#556075">{escaped}</text>'
        "</svg>"
    )
    return svg.encode("utf-8")


def _filter_catalog(query: str, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return catalog entries whose title or tags match ``query`` (case-insensitive)."""
    needle = query.lower()
    matches = [
        item
        for item in catalog
        if needle in str(item.get("title", "")).lower()
        or any(needle in str(tag).lower() for tag in item.get("tags", []))
    ]
    return sorted(matches, key=lambda item: str(item.get("title", "")))


async def _openverse_images(query: str, per_page: int) -> list[dict[str, Any]]:
    """Query the keyless Openverse images API and map results to catalog entries."""
    url = await asyncio.to_thread(validate_public_http_url, OPENVERSE_IMAGES_URL)
    params = {"q": query, "license_type": "commercial", "per_page": str(per_page)}
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()
    return [
        {
            "title": item.get("title") or "Untitled",
            "url": item.get("url") or "",
            "source": "openverse",
            "width": item.get("width", 0),
            "height": item.get("height", 0),
        }
        for item in payload.get("results", [])
    ]


async def _pexels_images(query: str, per_page: int) -> list[dict[str, Any]]:
    """Query the Pexels photos API and map results to catalog entries."""
    url = await asyncio.to_thread(validate_public_http_url, PEXELS_IMAGES_URL)
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": str(per_page)}
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    return [
        {
            "title": item.get("alt") or item.get("photographer") or "Untitled",
            "url": item.get("url") or "",
            "source": "pexels",
            "width": item.get("width", 0),
            "height": item.get("height", 0),
        }
        for item in payload.get("photos", [])
    ]


async def _pexels_videos(query: str, per_page: int) -> list[dict[str, Any]]:
    """Query the Pexels videos API and map results to catalog entries."""
    url = await asyncio.to_thread(validate_public_http_url, PEXELS_VIDEOS_URL)
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": str(per_page)}
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    return [
        {
            "title": item.get("url") or "Untitled",
            "url": item.get("url") or "",
            "source": "pexels",
            "duration_seconds": item.get("duration", 0),
        }
        for item in payload.get("videos", [])
    ]


async def graphic_art(
    prompt: str = Field(description="Text prompt describing the image to generate"),
    width: Annotated[int, Field(ge=256, le=2048, description="Image width in pixels")] = 1024,
    height: Annotated[int, Field(ge=256, le=2048, description="Image height in pixels")] = 1024,
    style: Annotated[str, Field(description="Optional style hint appended to the prompt")] = "",
) -> str:
    """Generate an image from a text prompt via Pollinations.ai (keyless).

    Saves the PNG to ``<workspace>/storage_files/media/`` and falls back to a local
    SVG placeholder when the network request fails.
    """
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    base_url = GRAPHIC_ART_PROVIDER_URL.format(prompt=quote_plus(prompt), style=quote_plus(style))
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}width={width}&height={height}&nologo=true&seed={time.time_ns()}"
    try:
        content = await _fetch_bytes(url)
        provider = "pollinations"
    except (httpx.HTTPError, OSError, ValueError):
        content = _svg_placeholder(prompt, width, height)
        provider = "local-fallback"
    path = _ensure_media_dir() / f"{_slug(prompt)}-{int(time.time())}.png"
    path.write_bytes(content)
    return json.dumps(
        {
            "status": "created",
            "provider": provider,
            "prompt": prompt,
            "file": str(path),
            "width": width,
            "height": height,
        },
        indent=2,
    )


async def search_template_images(
    query: str = Field(description="Search query for template images"),
    limit: Annotated[int, Field(ge=1, le=20, description="Number of results (1-20)")] = 5,
) -> str:
    """Search stock/template images.

    Uses Pexels when ``HIIL_PEXELS_API_KEY`` is set, otherwise the keyless Openverse
    API; falls back to the local catalog on any error.
    """
    if PEXELS_API_KEY:
        try:
            results = await _pexels_images(query, limit)
            provider = "pexels"
        except (httpx.HTTPError, OSError, ValueError):
            results = _filter_catalog(query, FALLBACK_IMAGES)[:limit]
            provider = "local-fallback"
    else:
        try:
            results = await _openverse_images(query, limit)
            provider = "openverse"
        except (httpx.HTTPError, OSError, ValueError):
            results = _filter_catalog(query, FALLBACK_IMAGES)[:limit]
            provider = "local-fallback"
    return json.dumps(
        {"query": query, "provider": provider, "count": len(results), "results": results},
        indent=2,
    )


async def search_template_videos(
    query: str = Field(description="Search query for template videos"),
    limit: Annotated[int, Field(ge=1, le=20, description="Number of results (1-20)")] = 5,
) -> str:
    """Search stock/template videos.

    Uses Pexels when ``HIIL_PEXELS_API_KEY`` is set; otherwise (or on error) returns
    the local catalog.
    """
    if PEXELS_API_KEY:
        try:
            results = await _pexels_videos(query, limit)
            provider = "pexels"
        except (httpx.HTTPError, OSError, ValueError):
            results = _filter_catalog(query, FALLBACK_VIDEOS)[:limit]
            provider = "local-fallback"
    else:
        results = _filter_catalog(query, FALLBACK_VIDEOS)[:limit]
        provider = "local-catalog"
    return json.dumps(
        {"query": query, "provider": provider, "count": len(results), "results": results},
        indent=2,
    )
