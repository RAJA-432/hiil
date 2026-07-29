from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any

from mcp_cli.services.logging import get_logger
from mcp_cli.services.sqlite_store import SqliteStore, asyncify

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

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


class IVFIndex:
    """Lightweight IVF index for approximate nearest neighbor search."""
    def __init__(self, n_clusters=32, n_probe=4, min_vectors_for_cluster=100):
        self.n_clusters = n_clusters
        self.n_probe = n_probe
        self.min_vectors = min_vectors_for_cluster
        self.centroids = None
        self.labels = None
        self.vectors_by_cluster = {}
        self.keys_by_cluster = {}
        self.namespace = None

    def build(self, embeddings, keys):
        """Build the index from a list of embeddings and corresponding keys."""
        if not _HAS_NUMPY or len(embeddings) < max(self.n_clusters, self.min_vectors):
            return False

        X = np.array(embeddings, dtype=np.float32)
        n = X.shape[0]
        k = min(self.n_clusters, n)

        rng = np.random.default_rng()
        idx = rng.choice(n, k, replace=False)
        centroids = X[idx].copy()

        for _ in range(10):
            dists = np.linalg.norm(X[:, np.newaxis] - centroids[np.newaxis, :], axis=2)
            labels = np.argmin(dists, axis=1)

            new_centroids = centroids.copy()
            for i in range(k):
                mask = labels == i
                if np.any(mask):
                    new_centroids[i] = X[mask].mean(axis=0)

            if np.allclose(centroids, new_centroids):
                centroids = new_centroids
                break
            centroids = new_centroids

        vectors_by_cluster = {}
        keys_by_cluster = {}
        for i, (label, key) in enumerate(zip(labels, keys)):
            lbl = int(label)
            vectors_by_cluster.setdefault(lbl, []).append(embeddings[i])
            keys_by_cluster.setdefault(lbl, []).append(key)

        self.centroids = centroids
        self.labels = labels
        self.vectors_by_cluster = vectors_by_cluster
        self.keys_by_cluster = keys_by_cluster
        return True

    def search(self, query_emb, limit=5):
        """Search the index, returning up to `limit` nearest neighbors."""
        if self.centroids is None:
            return []

        q = np.array(query_emb, dtype=np.float32)
        dists = np.linalg.norm(self.centroids - q, axis=1)
        nearest = np.argsort(dists)[:self.n_probe]

        candidates = []
        for idx in nearest:
            cluster_keys = self.keys_by_cluster.get(int(idx), [])
            cluster_vecs = self.vectors_by_cluster.get(int(idx), [])
            for key, vec in zip(cluster_keys, cluster_vecs):
                q_norm = np.linalg.norm(q)
                v_norm = np.linalg.norm(vec)
                score = float(np.dot(q, vec) / (q_norm * v_norm)) if q_norm and v_norm else 0.0
                candidates.append((score, key))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [k for _, k in candidates[:limit]]


class VectorStore(SqliteStore):
    _SCHEMA = [
        """CREATE TABLE IF NOT EXISTS vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namespace TEXT NOT NULL DEFAULT 'default',
            key TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            metadata TEXT DEFAULT '{}',
            UNIQUE(namespace, key)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_vec_ns ON vectors(namespace)",
    ]

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path.home() / ".hiil" / "vectors.db")
        super().__init__(db_path)
        self._ivf = IVFIndex()

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
        count = self.count(namespace)
        if count > 0 and count % 50 == 0 and _HAS_NUMPY:
            try:
                self._rebuild_ivf(namespace)
            except Exception:
                pass

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

    def _rebuild_ivf(self, namespace: str) -> None:
        """Rebuild the IVF index from all vectors in the given namespace."""
        rows = self._get_conn().execute(
            "SELECT key, embedding FROM vectors WHERE namespace=? ORDER BY id", (namespace,)
        ).fetchall()
        if not rows:
            return
        keys = [r[0] for r in rows]
        embeddings = [_decode_embedding(r[1]) for r in rows]
        self._ivf.build(embeddings, keys)
        self._ivf.namespace = namespace

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        """Return the top-k most similar vectors in a namespace ranked by cosine similarity.

        Uses the IVF index (fast path) when available, falling back to a full
        table scan + brute-force cosine similarity.
        """
        # Fast path: use IVF index
        if _HAS_NUMPY and self._ivf.centroids is not None and self._ivf.namespace == namespace:
            candidate_keys = self._ivf.search(query_embedding, limit=limit * 4)
            if len(candidate_keys) >= limit:
                placeholders = ",".join("?" for _ in candidate_keys)
                rows = self._get_conn().execute(
                    f"SELECT key, text, embedding, metadata FROM vectors WHERE namespace=? AND key IN ({placeholders})",  # noqa: S608
                    (namespace, *candidate_keys),
                ).fetchall()
                scored = []
                for key, text, emb_raw, meta_json in rows:
                    emb = _decode_embedding(emb_raw)
                    score = self._cosine_similarity(query_embedding, emb)
                    scored.append((score, key, text, json.loads(meta_json)))
                scored.sort(key=lambda x: x[0], reverse=True)
                return [
                    {"key": k, "text": t, "score": round(s, 4), "metadata": m}
                    for s, k, t, m in scored[:limit]
                ]

        # Fallback: brute-force (full table scan)
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

    @asyncify("list_keys")
    async def async_list_keys(self, namespace: str) -> list[str]:
        ...

    @asyncify("index")
    async def async_index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        ...

    @asyncify("delete")
    async def async_delete(self, namespace: str, key: str) -> bool:
        ...

    @asyncify("search")
    async def async_search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        ...
