from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_STORE_DIR = Path.home() / ".hiil" / "store"


class KVStore:
    """Simple file-backed key-value store with namespaces.

    Each namespace is a separate JSON file under ``~/.hiil/store/``.
    Thread-safe via a per-instance lock.
    """

    def __init__(self, store_dir: str | Path = _STORE_DIR):
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        ns = self._load(namespace)
        item = ns.get(key)
        if item is None:
            return None
        return dict(item)

    def get_many(self, namespace: str, keys: list[str]) -> list[dict[str, Any]]:
        ns = self._load(namespace)
        results = []
        for k in keys:
            item = ns.get(k)
            if item is not None:
                results.append(dict(item))
        return results

    def upsert(self, namespace: str, items: list[dict[str, Any]]) -> None:
        with self._lock:
            ns = self._load(namespace)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for item in items:
                key = item.get("key")
                if not key:
                    continue
                existing = ns.get(key, {})
                existing["value"] = item.get("value", {})
                existing["key"] = key
                existing["namespace"] = namespace
                existing["updated_at"] = now
                if "created_at" not in existing or not existing["created_at"]:
                    existing["created_at"] = now
                ns[key] = existing
            self._save(namespace, ns)

    def delete(self, namespace: str, keys: list[str]) -> int:
        with self._lock:
            ns = self._load(namespace)
            deleted = 0
            for k in keys:
                if k in ns:
                    del ns[k]
                    deleted += 1
            if deleted:
                self._save(namespace, ns)
            return deleted

    def search(self, namespace: str, filter_: dict[str, Any] | None = None,
               limit: int = 10) -> list[dict[str, Any]]:
        ns = self._load(namespace)
        results = list(ns.values())
        if filter_:
            def _match(item: dict[str, Any], f: dict[str, Any]) -> bool:
                val = item.get("value", {})
                for k, v in f.items():
                    if val.get(k) != v:
                        return False
                return True
            results = [r for r in results if _match(r, filter_)]
        results.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self, namespace: str) -> dict[str, dict[str, Any]]:
        if namespace in self._cache:
            return self._cache[namespace]
        path = self._dir / f"{namespace}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._cache[namespace] = data
        else:
            self._cache[namespace] = {}
        return self._cache[namespace]

    def _save(self, namespace: str, data: dict[str, dict[str, Any]]) -> None:
        path = self._dir / f"{namespace}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        self._cache[namespace] = dict(data)

    def list_namespaces(self) -> list[str]:
        return sorted({
            p.stem for p in self._dir.glob("*.json")
        })


_GLOBAL_STORE: KVStore | None = None


def get_store() -> KVStore:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = KVStore()
    return _GLOBAL_STORE
