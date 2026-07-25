from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import threading
import weakref
from pathlib import Path
from typing import Any


class VectorStore:
    def __init__(self, db_path: str | None = None):
        """Open a SQLite-backed vector store for embeddings, creating tables as needed."""
        if db_path is None:
            db_path = str(Path.home() / ".hiil" / "vectors.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()
        self._finalizer = weakref.finalize(self, self._close_conn, self._conn, self._lock)

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL DEFAULT 'default',
                key TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                UNIQUE(namespace, key)
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_vec_ns ON vectors(namespace)")
        self._conn.commit()

    def index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        """Insert or replace a vector entry in the given namespace."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO vectors (namespace, key, text, embedding, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (namespace, key, text, json.dumps(embedding), json.dumps(metadata or {})),
            )
            self._conn.commit()

    def delete(self, namespace: str, key: str) -> bool:
        """Remove a single vector entry by namespace and key; return True if deleted."""
        with self._lock:
            c = self._conn.execute("DELETE FROM vectors WHERE namespace=? AND key=?", (namespace, key))
            self._conn.commit()
            return c.rowcount > 0

    def delete_namespace(self, namespace: str) -> int:
        """Remove all vectors in a namespace and return the number deleted."""
        with self._lock:
            c = self._conn.execute("DELETE FROM vectors WHERE namespace=?", (namespace,))
            self._conn.commit()
            return c.rowcount

    def list_keys(self, namespace: str) -> list[str]:
        """Return all vector keys in the given namespace, ordered by insertion."""
        rows = self._conn.execute(
            "SELECT key FROM vectors WHERE namespace=? ORDER BY id", (namespace,)
        ).fetchall()
        return [r[0] for r in rows]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5) -> list[dict[str, Any]]:
        """Return the top-k most similar vectors in a namespace ranked by cosine similarity."""
        rows = self._conn.execute(
            "SELECT key, text, embedding, metadata FROM vectors WHERE namespace=?",
            (namespace,),
        ).fetchall()
        scored: list[tuple[float, str, str, dict]] = []
        for key, text, emb_json, meta_json in rows:
            emb = json.loads(emb_json)
            score = self._cosine_similarity(query_embedding, emb)
            scored.append((score, key, text, json.loads(meta_json)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"key": k, "text": t, "score": round(s, 4), "metadata": m}
            for s, k, t, m in scored[:limit]
        ]

    def count(self, namespace: str = "default") -> int:
        """Return the number of vectors stored in the given namespace."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM vectors WHERE namespace=?", (namespace,)
        ).fetchone()
        return row[0] if row else 0

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

    async def async_list_keys(self, namespace: str) -> list[str]:
        """List keys asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.list_keys, namespace)

    async def async_index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        """Index a vector asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.index, namespace, key, text, embedding, metadata)

    async def async_search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5) -> list[dict[str, Any]]:
        """Search vectors asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.search, query_embedding, namespace, limit)
