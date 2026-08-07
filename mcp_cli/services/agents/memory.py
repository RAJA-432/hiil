from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

MemoryNamespace = tuple[str, ...]


class MemoryScope:
    """Builds memory namespace tuples (Deep Agents store-backed scoping).

    Scope comes from which segments you include in the tuple — each
    combination is its own exact namespace, not an overlap of others.

    Common patterns:
    - Shared assistant:    ("memory", assistant_id)
    - Per-user:            ("memory", user_id)
    - Workspace:           ("memory", workspace_id)
    - User in workspace:   ("memory", workspace_id, user_id)
    - Assistant + user:    ("memory", assistant_id, user_id)
    """

    PREFIX = "memory"

    def __init__(self, *segments: str):
        if not segments:
            raise ValueError("MemoryScope requires at least one segment")
        self._segments = tuple(segments)

    @property
    def namespace(self) -> MemoryNamespace:
        return (self.PREFIX, *self._segments)

    @classmethod
    def assistant(cls, assistant_id: str) -> MemoryScope:
        return cls(assistant_id)

    @classmethod
    def user(cls, user_id: str) -> MemoryScope:
        return cls(user_id)

    @classmethod
    def workspace(cls, workspace_id: str) -> MemoryScope:
        return cls(workspace_id)

    @classmethod
    def user_in_workspace(cls, workspace_id: str, user_id: str) -> MemoryScope:
        return cls(workspace_id, user_id)

    @classmethod
    def assistant_user(cls, assistant_id: str, user_id: str) -> MemoryScope:
        return cls(assistant_id, user_id)

    def __str__(self) -> str:
        return "/".join(self.namespace)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, MemoryScope) and other.namespace == self.namespace

    def __hash__(self) -> int:
        return hash(self.namespace)


class AgentMemoryStore:
    """Persistent long-term memory with namespace-scoped storage.

    Memory is stored as files under ``store_dir/<namespace-segments>/``.
    A namespace (``MemoryNamespace``) determines which memory files the
    agent sees — mirroring Deep Agents' ``StoreBackend`` namespace model.

    For backward compatibility a bare ``agent_id`` is treated as a single
    segment namespace scoped to that agent.
    """

    def __init__(self, store_dir: str | Path):
        self._base = Path(store_dir).resolve()
        self._stat_cache: dict[tuple[MemoryNamespace, str], tuple[int, int, int]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, agent_id: str, path: str, namespace: MemoryNamespace | None = None) -> str | None:
        file_path = self._store_path(agent_id, path, namespace)
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def write(self, agent_id: str, path: str, content: str, namespace: MemoryNamespace | None = None) -> None:
        file_path = self._store_path(agent_id, path, namespace)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        ns = self._normalize_namespace(agent_id, namespace)
        self._stat_cache.pop((ns, path), None)

    def delete(self, agent_id: str, path: str, namespace: MemoryNamespace | None = None) -> bool:
        file_path = self._store_path(agent_id, path, namespace)
        if file_path.exists():
            file_path.unlink()
            ns = self._normalize_namespace(agent_id, namespace)
            self._stat_cache.pop((ns, path), None)
            return True
        return False

    def list_files(self, agent_id: str, namespace: MemoryNamespace | None = None) -> list[dict[str, Any]]:
        scope_dir = self._scope_dir(agent_id, namespace)
        if not scope_dir.exists():
            return []
        result = []
        for p in scope_dir.rglob("*"):
            if p.is_file():
                result.append({
                    "path": str(p.relative_to(scope_dir).as_posix()),
                    "size": p.stat().st_size,
                })
        return result

    def load_all(
        self,
        agent_id: str,
        memory_paths: list[str],
        namespace: MemoryNamespace | None = None,
    ) -> dict[str, str]:
        result = {}
        for mp in memory_paths:
            content = self.read(agent_id, mp, namespace=namespace)
            if content is not None:
                result[mp] = content
        return result

    def snapshot_hashes(
        self,
        agent_id: str,
        memory_paths: list[str],
        namespace: MemoryNamespace | None = None,
    ) -> dict[str, int]:
        ns = self._normalize_namespace(agent_id, namespace)
        hashes = {}
        for mp in memory_paths:
            file_path = self._store_path(agent_id, mp, namespace)
            key = (ns, mp)
            if file_path.exists():
                stat = file_path.stat()
                cached = self._stat_cache.get(key)
                if cached is not None and (cached[0], cached[1]) == (stat.st_mtime_ns, stat.st_size):
                    hashes[mp] = cached[2]
                else:
                    hashes[mp] = self._stable_hash(file_path.read_text(encoding="utf-8"))
                    self._stat_cache[key] = (stat.st_mtime_ns, stat.st_size, hashes[mp])
            else:
                hashes[mp] = 0
                self._stat_cache.pop(key, None)
        return hashes

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _stable_hash(content: str) -> int:
        return int.from_bytes(hashlib.sha256(content.encode("utf-8")).digest(), "big")

    def _normalize_namespace(self, agent_id: str, namespace: MemoryNamespace | None) -> MemoryNamespace:
        if namespace is not None:
            return namespace
        return ("agent", agent_id)

    def _scope_dir(self, agent_id: str, namespace: MemoryNamespace | None) -> Path:
        ns = self._normalize_namespace(agent_id, namespace)
        return self._base.joinpath(*ns)

    def _store_path(self, agent_id: str, path: str, namespace: MemoryNamespace | None) -> Path:
        scope_dir = self._scope_dir(agent_id, namespace)
        safe = scope_dir / path.lstrip("/").replace("\\", "/")
        resolved = safe.resolve()
        if scope_dir.resolve() not in resolved.parents and resolved != scope_dir.resolve():
            raise ValueError(f"Path traversal blocked: {path}")
        return resolved
