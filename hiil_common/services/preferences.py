"""Standalone long-term user-preference store.

Replicates the on-disk format of ``vajra_gate.services.preferences`` (which is
backed by ``vajra_gate.store.KVStore``) so that engine-written and gateway-written
preferences are the SAME file (``~/.hiil/store/preferences.json``, namespace
``"preferences"``). It does NOT import ``vajra_gate`` — a server using this
module can run without the gateway package installed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

_NAMESPACE = "preferences"
_DEFAULT_DIR = Path.home() / ".hiil" / "store"

logger = logging.getLogger("hiil_common.services.preferences")

_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class PreferencesStore:
    """File-backed key-value store for a single namespace, KVStore-compatible.

    Persists to ``<dir>/preferences.json`` in the same shape the gateway's
    ``KVStore`` writes: ``{user_id: {key, value, namespace, updated_at, created_at}}``.
    Thread-safe via a per-instance lock.
    """

    def __init__(self, store_dir: str | Path = _DEFAULT_DIR) -> None:
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _path(self) -> Path:
        return self._dir / f"{_NAMESPACE}.json"

    def _load(self) -> None:
        if not _NAMESPACE_RE.match(_NAMESPACE):
            raise ValueError(f"Invalid namespace: {_NAMESPACE!r}")
        path = self._path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Corrupt store file %s — starting empty", path)
                data = {}
            if isinstance(data, dict):
                self._data = data
            else:
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        path = self._path()
        tmp = path.with_name(f".{_NAMESPACE}.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)
        os.replace(tmp, path)

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._data.get(key)
            return dict(item) if item is not None else None

    def upsert(self, items: list[dict[str, Any]]) -> None:
        with self._lock:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for item in items:
                key = item.get("key")
                if not key:
                    continue
                existing = self._data.get(key, {})
                existing["value"] = item.get("value", {})
                existing["key"] = key
                existing["namespace"] = _NAMESPACE
                existing["updated_at"] = now
                if "created_at" not in existing or not existing["created_at"]:
                    existing["created_at"] = now
                self._data[key] = existing
            self._save()

    def delete(self, keys: list[str]) -> int:
        with self._lock:
            deleted = 0
            for k in keys:
                if k in self._data:
                    del self._data[k]
                    deleted += 1
            if deleted:
                self._save()
            return deleted


_GLOBAL_STORE: PreferencesStore | None = None


def get_store() -> PreferencesStore:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = PreferencesStore()
    return _GLOBAL_STORE


class UserPreferencesStore:
    """Shared long-term user-preference memory backed by the preferences JSON file.

    One entry per user in the ``preferences`` namespace
    (``~/.hiil/store/preferences.json``). Keyed by user rather than agent, so
    every server reads and writes the same user preferences across sessions.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        if store_dir is None:
            self._store = get_store()
        else:
            self._store = PreferencesStore(store_dir)

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        entry = self._store.get(user_id)
        if entry is None:
            return {}
        return dict(entry.get("value") or {})

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        prefs = self.get_preferences(user_id)
        prefs[key] = value
        self._store.upsert([{"key": user_id, "value": prefs}])

    def set_preferences(self, user_id: str, prefs: dict[str, Any]) -> None:
        merged = self.get_preferences(user_id)
        merged.update(prefs)
        self._store.upsert([{"key": user_id, "value": merged}])

    def delete_preference(self, user_id: str, key: str) -> bool:
        prefs = self.get_preferences(user_id)
        if key not in prefs:
            return False
        del prefs[key]
        if prefs:
            self._store.upsert([{"key": user_id, "value": prefs}])
        else:
            self._store.delete([user_id])
        return True

    def list_keys(self, user_id: str) -> list[str]:
        return sorted(self.get_preferences(user_id))
