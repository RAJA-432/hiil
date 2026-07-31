from datetime import datetime
from typing import Any

from mcp_cli.services.sqlite_store import SqliteStore, asyncify


class ChatHistoryManager(SqliteStore):
    _SCHEMA = [
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)",
    ]

    def __init__(self, db_path: str = "chat_history.db", max_sessions: int = 50):
        self._max_sessions = max_sessions
        super().__init__(db_path)
        self._get_conn().execute("PRAGMA synchronous=NORMAL")

    def save_message(self, session_id: str, role: str, content: str):
        """Persist a chat message to the database."""
        content = content or ""
        timestamp = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, timestamp)
            )
            conn.commit()
            self._prune_old_sessions()

    def load_session(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all messages for a session ordered by timestamp."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT id, role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            return [{"id": row[0], "role": row[1], "content": row[2] or "", "timestamp": row[3]} for row in cursor.fetchall()]

    def list_sessions(self, limit: int | None = None, offset: int = 0) -> list[str]:
        """Return session ids ordered by most recent activity, with optional pagination."""
        conn = self._get_conn()
        query = "SELECT session_id FROM messages GROUP BY session_id ORDER BY MAX(timestamp) DESC"
        params: list[int] = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            query += " OFFSET ?"
            params.append(offset)
        cursor = conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]

    def count_sessions(self) -> int:
        """Return the total number of sessions."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(DISTINCT session_id) FROM messages")
        return cursor.fetchone()[0]

    def delete_session(self, session_id: str) -> None:
        """Delete all messages for a session."""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()

    def search_messages(self, session_id: str, query: str) -> list[dict[str, Any]]:
        """Search messages in a session for a keyword."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? AND content LIKE ? ORDER BY timestamp ASC",
                (session_id, f"%{query}%")
            )
            return [{"role": row[0], "content": row[1] or ""} for row in cursor.fetchall()]

    def rename_session(self, old_id: str, new_id: str) -> bool:
        """Rename a session. Returns True if successful."""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE messages SET session_id = ? WHERE session_id = ?", (new_id, old_id)
        )
        conn.commit()
        return cursor.rowcount > 0

    def fork_session(self, source_id: str, target_id: str) -> int:
        """Copy all messages from source_id to target_id. Returns count copied."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (source_id,)
        )
        rows = cursor.fetchall()
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            [(target_id, r[0], r[1], r[2]) for r in rows]
        )
        conn.commit()
        return len(rows)

    def global_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search messages across all sessions. Returns results ordered by recency."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """SELECT id, session_id, role, content, timestamp
                   FROM messages
                   WHERE content LIKE ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (f"%{query}%", limit)
            )
            return [
                {"id": row[0], "session_id": row[1], "role": row[2], "content": row[3] or "", "timestamp": row[4]}
                for row in cursor.fetchall()
            ]

    def undo_last_messages(self, session_id: str, count: int = 2) -> int:
        """Remove the last N messages from a session. Returns number removed."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT id FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, count)
        )
        ids = [row[0] for row in cursor.fetchall()]
        if ids:
            conn.execute(
                f"DELETE FROM messages WHERE id IN ({','.join('?' * len(ids))})", ids  # noqa: S608 -- parameterized query, ? placeholders are safe
            )
            conn.commit()
        return len(ids)

    def _prune_old_sessions(self):
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT session_id, MAX(timestamp) FROM messages
            GROUP BY session_id ORDER BY MAX(timestamp) DESC
        """)
        sessions = [row[0] for row in cursor.fetchall()]
        if len(sessions) > self._max_sessions:
            for old in sessions[self._max_sessions:]:
                conn.execute("DELETE FROM messages WHERE session_id = ?", (old,))
            conn.commit()



    @asyncify("save_message")
    async def async_save_message(self, session_id: str, role: str, content: str):
        ...

    @asyncify("load_session")
    async def async_load_session(self, session_id: str) -> list[dict[str, Any]]:
        ...

    @asyncify("list_sessions")
    async def async_list_sessions(self, limit: int | None = None, offset: int = 0) -> list[str]:
        ...

    @asyncify("count_sessions")
    async def async_count_sessions(self) -> int:
        ...

    @asyncify("delete_session")
    async def async_delete_session(self, session_id: str) -> None:
        ...

    @asyncify("search_messages")
    async def async_search_messages(self, session_id: str, query: str) -> list[dict[str, Any]]:
        ...

    @asyncify("rename_session")
    async def async_rename_session(self, old_id: str, new_id: str) -> bool:
        ...

    @asyncify("fork_session")
    async def async_fork_session(self, source_id: str, target_id: str) -> int:
        ...

    @asyncify("global_search")
    async def async_global_search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        ...

    @asyncify("undo_last_messages")
    async def async_undo_last_messages(self, session_id: str, count: int = 2) -> int:
        ...
