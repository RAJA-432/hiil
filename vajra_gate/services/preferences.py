from __future__ import annotations

from pathlib import Path
from typing import Any

from vajra_gate.store import KVStore

_NAMESPACE = "preferences"


class UserPreferencesStore:
    """Shared long-term user-preference memory backed by the global KVStore.

    Preferences live in the ``preferences`` namespace of the global store
    (``~/.hiil/store/preferences.json``), one entry per user. Unlike the
    per-agent memory in ``mcp_cli.services.agents.memory``, this profile is
    keyed by user rather than agent, so EVERY agent reads and writes the same
    user preferences across sessions.
    """

    def __init__(self, store_dir: str | Path | None = None):
        if store_dir is None:
            from vajra_gate.store import get_store

            self._store = get_store()
        else:
            self._store = KVStore(store_dir)

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        entry = self._store.get(_NAMESPACE, user_id)
        if entry is None:
            return {}
        return dict(entry.get("value") or {})

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        prefs = self.get_preferences(user_id)
        prefs[key] = value
        self._store.upsert(_NAMESPACE, [{"key": user_id, "value": prefs}])

    def delete_preference(self, user_id: str, key: str) -> bool:
        prefs = self.get_preferences(user_id)
        if key not in prefs:
            return False
        del prefs[key]
        if prefs:
            self._store.upsert(_NAMESPACE, [{"key": user_id, "value": prefs}])
        else:
            self._store.delete(_NAMESPACE, [user_id])
        return True

    def list_keys(self, user_id: str) -> list[str]:
        return sorted(self.get_preferences(user_id))
