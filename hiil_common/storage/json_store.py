"""Thread-safe JSON file store shared by H.I.I.L. servers.

Moved verbatim from ``drishti_engine.storage.store``. ``drishti_engine.storage.store``
re-exports this class for backwards compatibility.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class JsonStore:
    """Per-user list-of-items store backed by a single JSON file."""

    def __init__(self, path: Path, *, seed: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, list[dict[str, Any]]] = {}
        if seed:
            self._data = {user: list(items) for user, items in seed.items()}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = raw
        except (OSError, ValueError):
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, self._path)

    def items_for(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._data.get(user_id, []))

    def add_item(self, user_id: str, item: dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault(user_id, []).append(item)
            self._save()

    def replace_all(self, user_id: str, items: list[dict[str, Any]]) -> None:
        with self._lock:
            self._data[user_id] = list(items)
            self._save()
