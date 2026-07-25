import asyncio
import sqlite3
import threading
import weakref
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: str
    session_id: str

class ChatHistoryManager:
    """Handles persistence of chat messages using a local SQLite database."""

    def __init__(self, db_path: str = "chat_history.db", max_sessions: int = 50):
        """Open a SQLite-backed chat history store with session pruning."""
        self.db_path = db_path
        self._max_sessions = max_sessions
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_db()
        self._finalizer = weakref.finalize(self, self._close_conn, self._conn, self._lock)

    def _get_conn(self) -> sqlite3.Connection:
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

    def rename_session(self, old_id: str, new_id: str) -> bool:
        """Rename a session and return True if any rows were updated."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE messages SET session_id = ? WHERE session_id = ?", (new_id, old_id)
            )
            conn.commit()
        return cursor.rowcount > 0

    def search_messages(self, session_id: str, query: str) -> list[dict[str, Any]]:
        """Find messages in a session whose content contains the query substring."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? AND content LIKE ? ORDER BY timestamp ASC",
            (session_id, f"%{query}%")
        )
        return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in cursor.fetchall()]

    def fork_session(self, source_id: str, target_id: str) -> int:
        """Copy all messages from one session into a new session and return the count."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
                (source_id,)
            )
            rows = cursor.fetchall()
            for role, content, ts in rows:
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (target_id, role, content, ts)
                )
            conn.commit()
        return len(rows)

    def undo_last_messages(self, session_id: str, count: int = 2) -> int:
        """Remove the most recent N messages from a session and return the number removed."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT id FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, count)
            )
            ids = [r[0] for r in cursor.fetchall()]
            if ids:
                conn.executemany(
                    "DELETE FROM messages WHERE id = ?", [(i,) for i in ids]
                )
                conn.commit()
        return len(ids)

    def delete_session(self, session_id: str):
        """Remove all messages belonging to the given session."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @staticmethod
    def _close_conn(conn: sqlite3.Connection | None, lock: threading.Lock) -> None:
        if conn is None:
            return
        with lock:
            try:
                conn.close()
            except Exception:
                pass

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

    async def async_search_messages(self, session_id: str, query: str) -> list[dict[str, Any]]:
        """Search messages asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.search_messages, session_id, query)

    async def async_fork_session(self, source_id: str, target_id: str) -> int:
        """Fork a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fork_session, source_id, target_id)

    async def async_undo_last_messages(self, session_id: str, count: int = 2) -> int:
        """Undo messages asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.undo_last_messages, session_id, count)

    async def async_rename_session(self, old_id: str, new_id: str) -> bool:
        """Rename a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.rename_session, old_id, new_id)

    async def async_delete_session(self, session_id: str):
        """Delete a session asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.delete_session, session_id)
