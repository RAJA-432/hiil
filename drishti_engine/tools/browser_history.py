"""Local browser-history search tools for the Drishti Engine MCP server.

Provides ``browser_search`` (read-only full-text search over the per-user
browsing history) and ``browser_add`` (write tool that records a page visit).
History lives per user in a JSON file at ``~/.hiil/store/browser_history.json``
(override with the ``HIIL_BROWSER_HISTORY_STORE`` env var). No external
credentials are required.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from pydantic import Field

from drishti_engine.config import BROWSER_HISTORY_STORE
from drishti_engine.data.browser_seed import DEFAULT_HISTORY
from drishti_engine.storage.store import JsonStore

_history_store: JsonStore | None = None


def _store() -> JsonStore:
    """Lazily create the shared per-user history store, seeded for ``default``."""
    global _history_store
    store = _history_store
    if store is None:
        store = JsonStore(Path(BROWSER_HISTORY_STORE), seed={"default": DEFAULT_HISTORY})
        _history_store = store
    return store


def _user_id(user_id: str) -> str:
    """Resolve the effective user id, honoring ``HIIL_USER_ID`` for ``default``."""
    return user_id if user_id != "default" else os.environ.get("HIIL_USER_ID", "default")


async def browser_search(
    query: str = Field(description="Substring to match against title, domain, url, or tags.", min_length=1),
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
    user_id: str = "default",
) -> str:
    """Full-text search of the locally stored browsing history.

    Case-insensitive substring match across title, domain, url, and tags.
    Results are ordered newest ``last_visit`` first and returned as JSON.

    Args:
        query: Non-empty search substring.
        limit: Maximum number of results to return (1-100).
        user_id: Owner of the history (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    needle = query.lower()
    matched = [
        item
        for item in _store().items_for(uid)
        if needle in item.get("title", "").lower()
        or needle in item.get("domain", "").lower()
        or needle in item.get("url", "").lower()
        or any(needle in tag.lower() for tag in item.get("tags", []))
    ]
    matched.sort(key=lambda item: item.get("last_visit", ""), reverse=True)
    results = matched[:limit]
    return json.dumps(
        {"user_id": uid, "query": query, "count": len(results), "results": results},
        indent=2,
    )


async def browser_add(
    title: str = Field(description="Page title to record."),
    url: str = Field(description="Page URL to record."),
    tags: str = "",
    user_id: str = "default",
) -> str:
    """Add a page to the local browsing history.

    Write tool — gated at the AgentConfig level; callers must be allowed to
    mutate the per-user history store.

    Args:
        title: Non-empty page title.
        url: Non-empty page URL.
        tags: Optional comma-separated tag list.
        user_id: Owner of the history (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    clean_title = title.strip()
    clean_url = url.strip()
    if not clean_title:
        raise ValueError("Title must not be empty.")
    if not clean_url:
        raise ValueError("URL must not be empty.")
    entry: dict[str, Any] = {
        "id": f"hist_{uuid.uuid4().hex[:8]}",
        "title": clean_title,
        "url": clean_url,
        "domain": urlparse(clean_url).netloc,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
        "last_visit": datetime.now(UTC).isoformat(),
        "visits": 1,
        "added_at": datetime.now(UTC).isoformat(),
    }
    _store().add_item(uid, entry)
    return json.dumps({"status": "added", "entry": entry}, indent=2)
