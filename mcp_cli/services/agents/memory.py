from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AgentMemoryStore:
    """Per-agent persistent memory: structured files that agents read/write.

    Each agent gets a namespaced directory under ``store_dir/<agent_id>/``.
    Memory files are injected into the agent's context before execution and
    persisted after writes.
    """

    def __init__(self, store_dir: str | Path):
        self._base = Path(store_dir).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, agent_id: str, path: str) -> str | None:
        file_path = self._agent_path(agent_id, path)
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def write(self, agent_id: str, path: str, content: str) -> None:
        file_path = self._agent_path(agent_id, path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    def delete(self, agent_id: str, path: str) -> bool:
        file_path = self._agent_path(agent_id, path)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_files(self, agent_id: str) -> list[dict[str, Any]]:
        agent_dir = self._base / agent_id
        if not agent_dir.exists():
            return []
        result = []
        for p in agent_dir.rglob("*"):
            if p.is_file():
                result.append({
                    "path": str(p.relative_to(agent_dir).as_posix()),
                    "size": p.stat().st_size,
                })
        return result

    def load_all(self, agent_id: str, memory_paths: list[str]) -> dict[str, str]:
        result = {}
        for mp in memory_paths:
            content = self.read(agent_id, mp)
            if content is not None:
                result[mp] = content
        return result

    def snapshot_hashes(self, agent_id: str, memory_paths: list[str]) -> dict[str, int]:
        hashes = {}
        for mp in memory_paths:
            content = self.read(agent_id, mp)
            if content is not None:
                hashes[mp] = hash(content)
            else:
                hashes[mp] = 0
        return hashes

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _agent_path(self, agent_id: str, path: str) -> Path:
        safe = self._base / agent_id / path.lstrip("/").replace("\\", "/")
        resolved = safe.resolve()
        expected = (self._base / agent_id).resolve()
        if expected not in resolved.parents and resolved != expected:
            raise ValueError(f"Path traversal blocked: {path}")
        return resolved
