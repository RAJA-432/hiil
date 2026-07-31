from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any

from mcp_cli.services.sqlite_store import SqliteStore, asyncify
from mcp_cli.services.vector_store import (
    _BATCH_SIZE,
    _decode_embedding,
    _encode_embedding,
)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class FaissVectorBackend(SqliteStore):
    """FAISS-backed vector store exposing the same interface as the sqlite backend."""

    _SCHEMA = [
        """CREATE TABLE IF NOT EXISTS faiss_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namespace TEXT NOT NULL DEFAULT 'default',
            key TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            metadata TEXT DEFAULT '{}',
            UNIQUE(namespace, key)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_faiss_vec_ns ON faiss_vectors(namespace)",
    ]

    def __init__(self, db_path: str | None = None):
        faiss_mod: Any = None
        np_mod: Any = None
        try:
            faiss_mod = importlib.import_module("faiss")
            np_mod = importlib.import_module("numpy")
        except ImportError as exc:
            raise RuntimeError("The 'faiss' backend requires the 'faiss' and 'numpy' packages") from exc
        self._faiss: Any = faiss_mod
        self._np: Any = np_mod
        if db_path is None:
            db_path = str(Path.home() / ".hiil" / "vectors.db")
        super().__init__(db_path)
        self._index_dir = Path(db_path).parent / "faiss_index"
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._indexes: dict[str, Any] = {}
        self._load_indexes()

    @classmethod
    def is_available(cls) -> bool:
        try:
            importlib.import_module("faiss")
            return True
        except ImportError:
            return False

    def _load_indexes(self) -> None:
        rows = self._get_conn().execute(
            "SELECT DISTINCT namespace FROM faiss_vectors"
        ).fetchall()
        for (namespace,) in rows:
            self._load_index(namespace)

    def _load_index(self, namespace: str) -> None:
        path = self._index_dir / f"{namespace}.index"
        if path.exists():
            self._indexes[namespace] = self._faiss.read_index(str(path))
        else:
            self._rebuild_index(namespace)

    def _rebuild_index(self, namespace: str) -> None:
        rows = self._get_conn().execute(
            "SELECT id, embedding FROM faiss_vectors WHERE namespace=? ORDER BY id",
            (namespace,),
        ).fetchall()
        path = self._index_dir / f"{namespace}.index"
        self._indexes.pop(namespace, None)
        if not rows:
            if path.exists():
                path.unlink()
            return
        dim = len(_decode_embedding(rows[0][1]))
        index = self._faiss.IndexIDMap(self._faiss.IndexFlatIP(dim))
        embeddings = self._np.asarray(
            [_l2_normalize(_decode_embedding(r[1])) for r in rows], dtype="float32"
        )
        ids = self._np.asarray([r[0] for r in rows], dtype="int64")
        index.add_with_ids(embeddings, ids)
        self._faiss.write_index(index, str(path))
        self._indexes[namespace] = index

    def index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        with self._lock:
            self._get_conn().execute(
                """INSERT OR REPLACE INTO faiss_vectors (namespace, key, text, embedding, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (namespace, key, text, _encode_embedding(embedding), json.dumps(metadata or {})),
            )
            self._get_conn().commit()
        self._rebuild_index(namespace)

    def delete(self, namespace: str, key: str) -> bool:
        with self._lock:
            c = self._get_conn().execute(
                "DELETE FROM faiss_vectors WHERE namespace=? AND key=?", (namespace, key)
            )
            self._get_conn().commit()
            deleted = c.rowcount > 0
        if deleted:
            self._rebuild_index(namespace)
        return deleted

    def delete_namespace(self, namespace: str) -> int:
        with self._lock:
            c = self._get_conn().execute("DELETE FROM faiss_vectors WHERE namespace=?", (namespace,))
            self._get_conn().commit()
            deleted = c.rowcount
        self._indexes.pop(namespace, None)
        path = self._index_dir / f"{namespace}.index"
        if path.exists():
            path.unlink()
        return deleted

    def list_keys(self, namespace: str) -> list[str]:
        rows = self._get_conn().execute(
            "SELECT key FROM faiss_vectors WHERE namespace=? ORDER BY id", (namespace,)
        ).fetchall()
        return [r[0] for r in rows]

    def search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        count = self.count(namespace)
        if count == 0:
            return []
        index = self._indexes.get(namespace)
        if index is None:
            self._rebuild_index(namespace)
            index = self._indexes.get(namespace)
        if index is None:
            return []
        k = min(limit, count)
        query = self._np.asarray([_l2_normalize(query_embedding)], dtype="float32")
        distances, ids = index.search(query, k)
        lookup: dict[int, Any] = {}
        for row_id in ids[0]:
            row = self._get_conn().execute(
                "SELECT key, text, metadata FROM faiss_vectors WHERE id=?", (int(row_id),)
            ).fetchone()
            if row is not None:
                lookup[int(row_id)] = row
        results: list[dict[str, Any]] = []
        for distance, row_id in zip(distances[0], ids[0]):
            row = lookup.get(int(row_id))
            if row is None:
                continue
            results.append(
                {
                    "key": row[0],
                    "text": row[1],
                    "score": round(float(distance), 4),
                    "metadata": json.loads(row[2]),
                }
            )
        return results

    def search_page(self, query_embedding: list[float], namespace: str = "default", offset: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT key, text, embedding, metadata FROM faiss_vectors WHERE namespace=? ORDER BY id LIMIT ? OFFSET ?",
            (namespace, limit, offset),
        ).fetchall()
        results = []
        for key, text, emb_raw, meta_json in rows:
            score = _cosine_similarity(query_embedding, _decode_embedding(emb_raw))
            results.append({"key": key, "text": text, "score": round(score, 4), "metadata": json.loads(meta_json)})
        return results

    def count(self, namespace: str = "default") -> int:
        row = self._get_conn().execute(
            "SELECT COUNT(*) FROM faiss_vectors WHERE namespace=?", (namespace,)
        ).fetchone()
        return row[0] if row else 0

    @asyncify("list_keys")
    async def async_list_keys(self, namespace: str) -> list[str]:
        return []

    @asyncify("index")
    async def async_index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        ...

    @asyncify("delete")
    async def async_delete(self, namespace: str, key: str) -> bool:
        return False

    @asyncify("search")
    async def async_search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        return []
