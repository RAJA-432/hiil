from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import Context

from hiil_common.services.preferences import UserPreferencesStore


def _user_id(u: str) -> str:
    return u if u != "default" else os.environ.get("HIIL_USER_ID", "default")


def _c(ctx: Context | None):
    return ctx or _NoopCtx()


class _NoopCtx:
    async def info(self, *a, **kw): pass
    async def warning(self, *a, **kw): pass
    async def error(self, *a, **kw): pass


def _store() -> UserPreferencesStore:
    return UserPreferencesStore()


def _fmt(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


async def remember(
    preferences: dict[str, Any],
    user_id: str = "default",
    ctx: Context | None = None,
) -> str:
    """Store or merge long-term user preferences, e.g. 'the user hates mushrooms'.

    Values may be any JSON-serialisable data (strings, numbers, lists, dicts).
    New keys are merged over existing ones; unrelated keys are never wiped.
    """
    c = _c(ctx)
    uid = _user_id(user_id)
    store = _store()
    store.set_preferences(uid, preferences)
    await c.info(f"Remembered {len(preferences)} preference(s) for user '{uid}'")
    return f"Remembered {len(preferences)} preference(s) for user '{uid}': {list(preferences)}"


async def recall(
    user_id: str = "default",
    keys: list[str] | None = None,
    ctx: Context | None = None,
) -> str:
    """Return stored user preferences as a readable summary (all keys or a subset)."""
    c = _c(ctx)
    uid = _user_id(user_id)
    prefs = _store().get_preferences(uid)
    if not prefs:
        await c.info(f"No preferences stored for user '{uid}'")
        return f"No preferences stored for user '{uid}'."
    if keys:
        prefs = {k: prefs[k] for k in keys if k in prefs}
    if not prefs:
        return f"No matching preferences for user '{uid}' among keys: {keys}"
    lines = "\n".join(f"- {k}: {_fmt(v)}" for k, v in sorted(prefs.items()))
    return f"Preferences for user '{uid}':\n{lines}"


async def forget(
    keys: list[str],
    user_id: str = "default",
    ctx: Context | None = None,
) -> str:
    """Remove stored user preferences by key."""
    c = _c(ctx)
    uid = _user_id(user_id)
    store = _store()
    removed = [k for k in keys if store.delete_preference(uid, k)]
    await c.info(f"Forgot {len(removed)} preference(s) for user '{uid}'")
    if not removed:
        return f"No preferences to forget for user '{uid}'. Requested keys: {keys}"
    return f"Forgot {len(removed)} preference(s) for user '{uid}': {removed}"
