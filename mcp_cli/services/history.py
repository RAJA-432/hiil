import asyncio
import sqlite3
import threading
import weakref
from datetime import datetime
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)




class ChatHistoryManager:
    """Handles persistence of chat messages using a local SQLite database."""

    def __init__(self, db_path: str = "chat_history.db", max_sessions: int = 50):
        """Open a SQLite-backed chat history store with session pruning."""
        self.db_path = db_path
        self._max_sessions = max_sessions
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_db()
        self._finalizer = weakref.finalize(self, self._close_conn, self._conn, self._lock)

    def _get_conn(self) -> sqlite3.Connection:
        assert self._conn is not None
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        conn.commit()

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
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        return [{"role": row[0], "content": row[1] or ""} for row in cursor.fetchall()]

    def list_sessions(self) -> list[str]:
        """Return all session ids ordered by most recent activity."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT session_id FROM messages GROUP BY session_id ORDER BY MAX(timestamp) DESC"
        )
        return [row[0] for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> None:
        """Delete all messages for a session."""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()

    def search_messages(self, session_id: str, query: str) -> list[dict[str, Any]]:
        """Search messages in a session for a keyword."""
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



    @staticmethod
    def _close_conn(conn: sqlite3.Connection | None, lock: threading.Lock) -> None:
        if conn is None:
            return
        with lock:
            try:
                conn.close()
            except Exception:
                logger.warning("Failed to close history database connection")

    def close(self):
        """Close the database connection."""
        if hasattr(self, "_finalizer"):
            self._finalizer()
        self._conn = None

    async def async_save_message(self, session_id: str, role: str, content: str):
        """Save a message asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.save_message, session_id, role, content)

    async def async_load_session(self, session_id: str) -> list[dict[str, Any]]:
        """Load a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.load_session, session_id)

    async def async_list_sessions(self) -> list[str]:
        """List sessions asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.list_sessions)

    async def async_delete_session(self, session_id: str) -> None:
        """Delete a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.delete_session, session_id)

    async def async_search_messages(self, session_id: str, query: str) -> list[dict[str, Any]]:
        """Search messages asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.search_messages, session_id, query)

    async def async_rename_session(self, old_id: str, new_id: str) -> bool:
        """Rename a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.rename_session, old_id, new_id)

    async def async_fork_session(self, source_id: str, target_id: str) -> int:
        """Fork a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fork_session, source_id, target_id)

    async def async_undo_last_messages(self, session_id: str, count: int = 2) -> int:
        """Undo last messages asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.undo_last_messages, session_id, count)



