from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import struct
import threading
import weakref
from pathlib import Path
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 500


def _decode_embedding(raw: str | bytes) -> list[float]:
    if isinstance(raw, bytes):
        n = len(raw) // 4
        return list(struct.unpack(f"<{n}f", raw))
    if isinstance(raw, str) and raw.startswith("["):
        return json.loads(raw)
    return json.loads(raw)


def _encode_embedding(emb: list[float]) -> bytes:
    return struct.pack(f"<{len(emb)}f", *emb)


class VectorStore:
    def __init__(self, db_path: str | None = None):
        """Open a SQLite-backed vector store for embeddings, creating tables as needed."""
        if db_path is None:
            db_path = str(Path.home() / ".hiil" / "vectors.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = sqlite3.connect(db_path, check_same_thread=False)
        self._get_conn().execute("PRAGMA journal_mode=WAL")
        self._init_db()
        self._finalizer = weakref.finalize(self, self._close_conn, self._conn, self._lock)

    def _get_conn(self) -> sqlite3.Connection:
        assert self._conn is not None
        return self._conn

    def _init_db(self):
        self._get_conn().execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL DEFAULT 'default',
                key TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                metadata TEXT DEFAULT '{}',
                UNIQUE(namespace, key)
            )
        """)
        self._get_conn().execute("CREATE INDEX IF NOT EXISTS idx_vec_ns ON vectors(namespace)")
        self._get_conn().commit()

    def index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        """Insert or replace a vector entry in the given namespace."""
        blob = _encode_embedding(embedding)
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO vectors (namespace, key, text, embedding, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (namespace, key, text, blob, json.dumps(metadata or {})),
            )
            self._get_conn().commit()

    def delete(self, namespace: str, key: str) -> bool:
        """Remove a single vector entry by namespace and key; return True if deleted."""
        with self._lock:
            c = self._get_conn().execute("DELETE FROM vectors WHERE namespace=? AND key=?", (namespace, key))
            self._get_conn().commit()
            return c.rowcount > 0

    def delete_namespace(self, namespace: str) -> int:
        """Remove all vectors in a namespace and return the number deleted."""
        with self._lock:
            c = self._get_conn().execute("DELETE FROM vectors WHERE namespace=?", (namespace,))
            self._get_conn().commit()
            return c.rowcount

    def list_keys(self, namespace: str) -> list[str]:
        """Return all vector keys in the given namespace, ordered by insertion."""
        rows = self._get_conn().execute(
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

    def search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        """Return the top-k most similar vectors in a namespace ranked by cosine similarity.

        Loads vectors in batches to avoid loading the entire embedding table into RAM.
        """
        scored: list[tuple[float, str, str, dict]] = []
        offset = 0
        while True:
            rows = self._get_conn().execute(
                "SELECT key, text, embedding, metadata FROM vectors WHERE namespace=? ORDER BY id LIMIT ? OFFSET ?",
                (namespace, batch_size, offset),
            ).fetchall()
            if not rows:
                break
            for key, text, emb_raw, meta_json in rows:
                emb = _decode_embedding(emb_raw)
                score = self._cosine_similarity(query_embedding, emb)
                scored.append((score, key, text, json.loads(meta_json)))
            offset += len(rows)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"key": k, "text": t, "score": round(s, 4), "metadata": m}
            for s, k, t, m in scored[:limit]
        ]

    def search_page(self, query_embedding: list[float], namespace: str = "default", offset: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        """Return a page of vectors with computed similarity scores, ordered by id."""
        rows = self._get_conn().execute(
            "SELECT key, text, embedding, metadata FROM vectors WHERE namespace=? ORDER BY id LIMIT ? OFFSET ?",
            (namespace, limit, offset),
        ).fetchall()
        results = []
        for key, text, emb_raw, meta_json in rows:
            emb = _decode_embedding(emb_raw)
            score = self._cosine_similarity(query_embedding, emb)
            results.append({"key": key, "text": text, "score": round(score, 4), "metadata": json.loads(meta_json)})
        return results

    def count(self, namespace: str = "default") -> int:
        """Return the number of vectors stored in the given namespace."""
        row = self._get_conn().execute(
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
                logger.warning("Failed to close vector store database connection")

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

    async def async_delete(self, namespace: str, key: str) -> bool:
        """Delete a vector asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.delete, namespace, key)

    async def async_search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        """Search vectors asynchronously via the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.search, query_embedding, namespace, limit, batch_size)
