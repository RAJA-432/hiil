from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

_STORE_DIR = Path.home() / ".hiil" / "store"

_REWARD_NAMESPACE = "rewards"

_REWARDS_COMPACT_THRESHOLD = 1024 * 1024  # 1 MB

logger = logging.getLogger("vajra_gate.store")


class KVStore:
    """Simple file-backed key-value store with namespaces.

    Each namespace is a separate JSON file under ``~/.hiil/store/``. The
    ``rewards`` namespace is an append-only JSONL log (``rewards.jsonl``) so
    that high-frequency reward events cost O(1) per write instead of
    rewriting the whole file. Thread-safe via a per-instance lock.
    """

    _NAMESPACE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

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
        if namespace == _REWARD_NAMESPACE:
            self._upsert_rewards(items)
            return
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

    def all_items(self, namespace: str) -> list[dict[str, Any]]:
        """Return every item in a namespace without a row cap.

        Used by metrics that must aggregate over the full event log rather than
        a paginated slice.
        """
        ns = self._load(namespace)
        return list(ns.values())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_namespace(namespace: str) -> None:
        if not KVStore._NAMESPACE_RE.match(namespace):
            raise ValueError(f"Invalid namespace: {namespace!r}")

    def _load(self, namespace: str) -> dict[str, dict[str, Any]]:
        self._validate_namespace(namespace)
        if namespace in self._cache:
            return self._cache[namespace]
        if namespace == _REWARD_NAMESPACE:
            self._cache[namespace] = self._load_rewards()
            return self._cache[namespace]
        path = self._dir / f"{namespace}.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Corrupt store file %s — starting empty", path)
                try:
                    corrupt = path.read_text(encoding="utf-8", errors="replace")
                    (self._dir / f"{namespace}.json.corrupt").write_text(corrupt, encoding="utf-8")
                except Exception:
                    pass
                data = {}
            self._cache[namespace] = data
        else:
            self._cache[namespace] = {}
        return self._cache[namespace]

    def _save(self, namespace: str, data: dict[str, dict[str, Any]]) -> None:
        self._validate_namespace(namespace)
        if namespace == _REWARD_NAMESPACE:
            self._write_rewards(data)
            self._cache[namespace] = dict(data)
            return
        path = self._dir / f"{namespace}.json"
        tmp = path.with_name(f".{namespace}.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, path)
        self._cache[namespace] = dict(data)

    # ------------------------------------------------------------------
    # Append-only rewards log
    # ------------------------------------------------------------------

    def _rewards_path(self) -> Path:
        return self._dir / "rewards.jsonl"

    def _load_rewards(self) -> dict[str, dict[str, Any]]:
        cache: dict[str, dict[str, Any]] = {}
        path = self._rewards_path()
        if path.exists():
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if "key" in entry:
                    key = entry.get("key")
                    if key:
                        cache[key] = entry
                else:
                    # Compacted snapshot: {key: entry}
                    for key, item in entry.items():
                        if isinstance(item, dict) and item.get("key"):
                            cache[key] = item
        legacy = self._dir / "rewards.json"
        if legacy.exists():
            with open(legacy, encoding="utf-8") as f:
                data = json.load(f)
            for key, entry in data.items():
                cache.setdefault(key, entry)
            self._write_rewards(cache)
            legacy.unlink(missing_ok=True)
        return cache

    def _write_rewards(self, cache: dict[str, dict[str, Any]]) -> None:
        path = self._rewards_path()
        tmp = path.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, default=str, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)

    def _upsert_rewards(self, items: list[dict[str, Any]]) -> None:
        with self._lock:
            ns = self._load(_REWARD_NAMESPACE)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            appended: list[dict[str, Any]] = []
            for item in items:
                key = item.get("key")
                if not key:
                    continue
                existing = ns.get(key, {})
                existing["value"] = item.get("value", {})
                existing["key"] = key
                existing["namespace"] = _REWARD_NAMESPACE
                existing["updated_at"] = now
                if "created_at" not in existing or not existing["created_at"]:
                    existing["created_at"] = now
                ns[key] = existing
                appended.append(existing)
            if not appended:
                return
            path = self._rewards_path()
            if path.exists() and path.stat().st_size > _REWARDS_COMPACT_THRESHOLD:
                # Compact: rewrite the latest-state snapshot and skip the append
                # (the appended entries are already part of the snapshot).
                self._write_rewards(ns)
                return
            with open(path, "a", encoding="utf-8") as f:
                for entry in appended:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def list_namespaces(self) -> list[str]:
        return sorted({
            p.stem for p in self._dir.glob("*.json")
        } | {
            p.stem for p in self._dir.glob("*.jsonl")
        })


_GLOBAL_STORE: KVStore | None = None


def get_store() -> KVStore:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = KVStore()
    return _GLOBAL_STORE
