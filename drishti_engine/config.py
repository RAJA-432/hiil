"""Shared configuration constants for the Drishti Engine MCP server.

Centralizes env-driven values the individual tool modules consume. Keep it
small — only move a constant here when more than one module could use it.
"""

from __future__ import annotations

import os
from pathlib import Path

from hiil_common.config import WORKSPACE_ROOT  # loads dotenv, unifies HIIL_WORKSPACE_DIR

# Generated artwork is written under the workspace's storage_files dir.
MEDIA_DIR: Path = WORKSPACE_ROOT / "storage_files" / "media"

# Local browser-history store (mirrors setu_bridge calendar/mail stores).
_DEFAULT_HISTORY_STORE = Path.home() / ".hiil" / "store" / "browser_history.json"
BROWSER_HISTORY_STORE = os.environ.get("HIIL_BROWSER_HISTORY_STORE") or str(_DEFAULT_HISTORY_STORE)

# Optional API keys (never hardcoded — env vars only).
PEXELS_API_KEY = os.environ.get("HIIL_PEXELS_API_KEY", "").strip()

# Keyless image generation provider (Pollinations.ai). The ``{prompt}`` and
# ``{style}`` placeholders are URL-encoded before substitution.
GRAPHIC_ART_PROVIDER_URL = os.environ.get(
    "HIIL_GRAPHIC_ART_URL",
    "https://image.pollinations.ai/prompt/{prompt}",
)

# Stock-template search endpoints.
OPENVERSE_IMAGES_URL = "https://api.openverse.org/v1/images/"
PEXELS_IMAGES_URL = "https://api.pexels.com/v1/search/"
PEXELS_VIDEOS_URL = "https://api.pexels.com/v1/videos/search/"
