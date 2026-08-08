from __future__ import annotations

from datetime import datetime
from typing import Any


class SessionManager:
    def __init__(self, chat: Any) -> None:
        self.chat = chat

    @property
    def history(self) -> Any:
        return self.chat.history

    def new_session(self) -> str:
        from mcp_cli.services.chat import new_session_id
        sid = new_session_id()
        self.chat.session_id = sid
        self.chat.messages = []
        return sid

    def export_transcript(self) -> str:
        lines = []
        for m in self.chat.messages:
            role = m.get("role", "?")
            content = m.get("content", "")
            lines.append(f"[{role}]\n{content}\n")
        return "\n".join(lines)

    async def switch(self, session_id: str) -> None:
        sid = session_id.strip()
        if not sid:
            return
        self.chat.session_id = sid
        self.chat.messages = await self.history.async_load_session(sid)

    async def load_session(self, session_id: str) -> list[dict[str, Any]]:
        return await self.history.async_load_session(session_id)

    async def list_sessions(self) -> list[str]:
        return await self.history.async_list_sessions()

    async def rename(self, name: str) -> bool:
        old = self.chat.session_id
        if await self.history.async_rename_session(old, name):
            self.chat.session_id = name
            return True
        return False

    async def fork(self, session_id: str) -> tuple[int, str]:
        new_id = f"fork_{session_id}_{datetime.now().strftime('%H%M%S')}"
        count = await self.history.async_fork_session(session_id, new_id)
        if count:
            self.chat.session_id = new_id
            self.chat.messages = await self.history.async_load_session(new_id)
        return count, new_id

    async def undo(self, count: int = 2) -> int:
        removed = await self.history.async_undo_last_messages(self.chat.session_id, count)
        if removed:
            self.chat.messages = await self.history.async_load_session(self.chat.session_id)
        return removed
