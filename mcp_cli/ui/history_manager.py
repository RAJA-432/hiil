from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Protocol

from mcp_cli.services.history import ChatHistoryManager

# ── Plugin system ────────────────────────────────────────────────────────


class MessageRenderer(ABC):
    """Abstract base for a plugin that renders a single message to a string."""

    @abstractmethod
    def render(self, msg: dict[str, Any]) -> str:
        ...


class RenderFn(Protocol):
    def __call__(self, msg: dict[str, Any]) -> str:
        ...


class _FuncRenderer(MessageRenderer):
    def __init__(self, fn: RenderFn):
        self._fn = fn

    def render(self, msg: dict[str, Any]) -> str:
        return self._fn(msg)


# ── HistoryManager ──────────────────────────────────────────────────────


class HistoryManager:
    """High-level wrapper around ``ChatHistoryManager`` with search
    filtering, export, and pluggable rendering.

    Usage::

        hm = HistoryManager()
        hm.save("sess-1", "user", "hello")
        msgs = hm.search("sess-1", "hello", regex=False)
        print(hm.export_json("sess-1"))
    """

    def __init__(self, db_path: str = "chat_history.db", max_sessions: int = 50):
        self._db = ChatHistoryManager(db_path=db_path, max_sessions=max_sessions)
        self._renderers: dict[str, MessageRenderer] = {}

    # ── Persistence (delegated) ─────────────────────────────────────────

    def save(self, session_id: str, role: str, content: str) -> None:
        self._db.save_message(session_id, role, content)

    def load(self, session_id: str) -> list[dict[str, Any]]:
        return self._db.load_session(session_id)

    def list_sessions(self) -> list[str]:
        return self._db.list_sessions()

    def rename(self, old_id: str, new_id: str) -> bool:
        return self._db.rename_session(old_id, new_id)

    def fork(self, source_id: str, target_id: str) -> int:
        return self._db.fork_session(source_id, target_id)

    def undo(self, session_id: str, count: int = 2) -> int:
        return self._db.undo_last_messages(session_id, count)

    def delete(self, session_id: str) -> None:
        self._db.delete_session(session_id)

    def close(self) -> None:
        self._db.close()

    # ── Async wrappers ──────────────────────────────────────────────────

    async def async_save(self, session_id: str, role: str, content: str) -> None:
        await self._db.async_save_message(session_id, role, content)

    async def async_load(self, session_id: str) -> list[dict[str, Any]]:
        return await self._db.async_load_session(session_id)

    async def async_list(self) -> list[str]:
        return await self._db.async_list_sessions()

    async def async_search(self, session_id: str, query: str) -> list[dict[str, Any]]:
        return await self._db.async_search_messages(session_id, query)

    async def async_fork(self, source_id: str, target_id: str) -> int:
        return await self._db.async_fork_session(source_id, target_id)

    async def async_undo(self, session_id: str, count: int = 2) -> int:
        return await self._db.async_undo_last_messages(session_id, count)

    async def async_rename(self, old_id: str, new_id: str) -> bool:
        return await self._db.async_rename_session(old_id, new_id)

    async def async_delete(self, session_id: str) -> None:
        await self._db.async_delete_session(session_id)

    # ── Enhanced search ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        session_id: str | None = None,
        *,
        regex: bool = False,
        roles: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Flexible search with optional regex and role filtering.

        When *session_id* is ``None``, searches across **all** sessions.
        When *regex* is ``True``, the query is treated as a regex pattern.
        """
        sessions = [session_id] if session_id else self.list_sessions()
        results: list[dict[str, Any]] = []

        for sid in sessions:
            if regex:
                msgs = self.load(sid)
            elif session_id:
                msgs = self._db.search_messages(sid, query)
            else:
                msgs = self.load(sid)

            for m in msgs:
                m["session_id"] = sid
                content = m.get("content", "")

                if regex:
                    try:
                        if not re.search(query, content):
                            continue
                    except re.error:
                        continue
                elif session_id is None:
                    if query.lower() not in content.lower():
                        continue

                if roles and m.get("role") not in roles:
                    continue

                results.append(m)

        results.sort(key=lambda x: x.get("timestamp", ""))
        return results

    # ── Plugin system ───────────────────────────────────────────────────

    def register_renderer(self, name: str, renderer: MessageRenderer | RenderFn) -> None:
        if not isinstance(renderer, MessageRenderer):
            renderer = _FuncRenderer(renderer)
        self._renderers[name] = renderer

    def unregister_renderer(self, name: str) -> bool:
        return bool(self._renderers.pop(name, None))

    def render_messages(
        self,
        messages: list[dict[str, Any]],
        renderer_name: str | None = None,
        limit: int = 0,
    ) -> list[str]:
        """Render a list of messages using a named renderer (or a default
        plain-text renderer)."""
        if renderer_name and renderer_name in self._renderers:
            r = self._renderers[renderer_name]
        else:
            r = _FuncRenderer(lambda m: f"{m['role']}: {m['content'][:200]}")

        if limit:
            messages = messages[-limit:]

        return [r.render(m) for m in messages]

    # ── Export ──────────────────────────────────────────────────────────

    def export_json(self, session_id: str, filepath: str | None = None) -> str:
        """Export a session to JSON (returns the string; writes to file
        if *filepath* given)."""
        msgs = self.load(session_id)
        data = {
            "session_id": session_id,
            "exported_at": datetime.now().isoformat(),
            "messages": msgs,
        }
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
        return text

    def export_markdown(self, session_id: str, filepath: str | None = None) -> str:
        """Export a session as Markdown transcript."""
        msgs = self.load(session_id)
        lines = [
            f"# Chat Transcript: `{session_id}`",
            f"_Exported: {datetime.now().isoformat()}_",
            "",
            "---",
            "",
        ]
        for m in msgs:
            role = m["role"].upper()
            content = m["content"]
            lines.append(f"### {role}")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")

        text = "\n".join(lines)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
        return text
