from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Protocol

from mcp_cli.services.logging import get_logger
from mcp_cli.services.sqlite_store import SqliteStore, asyncify

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

logger = get_logger(__name__)

_BATCH_SIZE = 500

_IVF_N_CLUSTERS = 32
_IVF_N_PROBE = 4
_IVF_MIN_VECTORS = 100

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase a string and split it into alphanumeric tokens."""
    return _TOKEN_RE.findall(text.lower())


def _min_max_normalize(values: list[float]) -> list[float]:
    """Scale a list of floats to the inclusive 0..1 range via min-max."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


class BM25Scorer:
    """Pure-Python Okapi BM25 scorer over a corpus of documents (no numpy needed)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_freq: dict[str, int] = {}
        self._doc_lens: list[int] = []
        self._tokenized: list[list[str]] = []

    def fit(self, documents: list[str]) -> BM25Scorer:
        """Precompute corpus statistics (lengths, average length, term document frequency)."""
        self._tokenized = [_tokenize(d) for d in documents]
        self._doc_lens = [len(toks) for toks in self._tokenized]
        self.corpus_size = len(documents)
        self.avg_doc_len = sum(self._doc_lens) / self.corpus_size if self.corpus_size else 0.0
        doc_freq: dict[str, int] = {}
        for toks in self._tokenized:
            for term in set(toks):
                doc_freq[term] = doc_freq.get(term, 0) + 1
        self.doc_freq = doc_freq
        return self

    def _idf(self, term: str) -> float:
        if self.corpus_size == 0:
            return 0.0
        df = self.doc_freq.get(term, 0)
        return math.log(1 + (self.corpus_size - df + 0.5) / (df + 0.5))

    def score(self, query: str, doc_idx: int) -> float:
        """Return the BM25 score of the query against the document at `doc_idx`."""
        if self.corpus_size == 0 or not (0 <= doc_idx < self.corpus_size):
            return 0.0
        query_terms = _tokenize(query)
        if not query_terms:
            return 0.0
        toks = self._tokenized[doc_idx]
        dl = self._doc_lens[doc_idx]
        term_freq: dict[str, int] = {}
        for term in toks:
            term_freq[term] = term_freq.get(term, 0) + 1
        score = 0.0
        for term in set(query_terms):
            freq = term_freq.get(term, 0)
            if freq == 0:
                continue
            denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avg_doc_len)
            score += self._idf(term) * (freq * (self.k1 + 1)) / denom
        return score

    def rank(self, query: str, documents: list[str]) -> list[tuple[float, int]]:
        """Score every document against the query, returning (score, index) pairs sorted desc."""
        self.fit(documents)
        scored = [(self.score(query, i), i) for i in range(self.corpus_size)]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored


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
    def __init__(self, n_clusters=_IVF_N_CLUSTERS, n_probe=_IVF_N_PROBE, min_vectors_for_cluster=_IVF_MIN_VECTORS):
        self.n_clusters = n_clusters
        self.n_probe = n_probe
        self.min_vectors = min_vectors_for_cluster
        self.centroids = None
        self.labels = None
        self.vectors_by_cluster = {}
        self.keys_by_cluster = {}
        self.namespace = None

    def reset(self) -> None:
        """Drop any in-memory index state so searches fall back to brute force."""
        self.centroids = None
        self.labels = None
        self.vectors_by_cluster = {}
        self.keys_by_cluster = {}
        self.namespace = None

    def build(self, embeddings, keys):
        """Build the index from a list of embeddings and corresponding keys."""
        if not _HAS_NUMPY or len(embeddings) < max(self.n_clusters, self.min_vectors):
            return False

        x = np.array(embeddings, dtype=np.float32)
        n = x.shape[0]
        k = min(self.n_clusters, n)

        rng = np.random.default_rng()
        idx = rng.choice(n, k, replace=False)
        centroids = x[idx].copy()

        for _ in range(10):
            dists = np.linalg.norm(x[:, np.newaxis] - centroids[np.newaxis, :], axis=2)
            labels = np.argmin(dists, axis=1)

            new_centroids = centroids.copy()
            for i in range(k):
                mask = labels == i
                if np.any(mask):
                    new_centroids[i] = x[mask].mean(axis=0)

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


class VectorBackend(Protocol):
    """Duck-type interface shared by all vector store backends."""

    def index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None: ...
    def delete(self, namespace: str, key: str) -> bool: ...
    def delete_namespace(self, namespace: str) -> int: ...
    def list_keys(self, namespace: str) -> list[str]: ...
    def search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]: ...
    def search_page(self, query_embedding: list[float], namespace: str = "default", offset: int = 0, limit: int = 20) -> list[dict[str, Any]]: ...
    def count(self, namespace: str = "default") -> int: ...
    def close(self) -> None: ...

    async def async_list_keys(self, namespace: str) -> list[str]: ...
    async def async_index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict | None = None) -> None: ...
    async def async_delete(self, namespace: str, key: str) -> bool: ...
    async def async_search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = _BATCH_SIZE) -> list[dict[str, Any]]: ...


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

    def __init__(
        self,
        db_path: str | None = None,
        ivf_n_clusters: int | None = None,
        ivf_n_probe: int | None = None,
        ivf_min_vectors: int | None = None,
    ):
        if db_path is None:
            db_path = str(Path.home() / ".hiil" / "vectors.db")
        super().__init__(db_path)
        self._ivf_n_clusters = _IVF_N_CLUSTERS if ivf_n_clusters is None else ivf_n_clusters
        self._ivf_n_probe = _IVF_N_PROBE if ivf_n_probe is None else ivf_n_probe
        self._ivf_min_vectors = _IVF_MIN_VECTORS if ivf_min_vectors is None else ivf_min_vectors
        self._ivf = IVFIndex(
            n_clusters=self._ivf_n_clusters,
            n_probe=self._ivf_n_probe,
            min_vectors_for_cluster=self._ivf_min_vectors,
        )

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

    def _tune_params(self, count: int) -> tuple[int, int]:
        """Pick n_clusters/n_probe adaptively so clustering scales with corpus size."""
        if count >= 50:
            n_clusters = min(self._ivf_n_clusters, max(1, round(math.sqrt(count))))
            n_probe = max(1, min(n_clusters, int(n_clusters * 0.1)))
            return n_clusters, n_probe
        return self._ivf_n_clusters, self._ivf_n_probe

    def _rebuild_ivf(self, namespace: str) -> None:
        """Rebuild the IVF index from all vectors in the given namespace."""
        rows = self._get_conn().execute(
            "SELECT key, embedding FROM vectors WHERE namespace=? ORDER BY id", (namespace,)
        ).fetchall()
        if not rows:
            return
        keys = [r[0] for r in rows]
        embeddings = [_decode_embedding(r[1]) for r in rows]
        n_clusters, n_probe = self._tune_params(len(rows))
        self._ivf.n_clusters = n_clusters
        self._ivf.n_probe = n_probe
        if self._ivf.build(embeddings, keys):
            self._ivf.namespace = namespace
        else:
            self._ivf.reset()

    def tune(self, namespace: str = "default") -> dict[str, Any]:
        """Adaptively size the IVF index for the current corpus and rebuild it."""
        n_clusters, n_probe = self._tune_params(self.count(namespace))
        self._ivf.n_clusters = n_clusters
        self._ivf.n_probe = n_probe
        self._rebuild_ivf(namespace)
        return self.ivf_stats(namespace)

    def ivf_stats(self, namespace: str = "default") -> dict[str, Any]:
        """Return observability stats about the IVF index for a namespace."""
        return {
            "count": self.count(namespace),
            "n_clusters": self._ivf.n_clusters,
            "n_probe": self._ivf.n_probe,
            "has_index": (
                _HAS_NUMPY
                and self._ivf.centroids is not None
                and self._ivf.namespace == namespace
            ),
        }

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
                fast_scored: list[tuple[float, str, str, dict]] = []
                for key, text, emb_raw, meta_json in rows:
                    emb = _decode_embedding(emb_raw)
                    score = self._cosine_similarity(query_embedding, emb)
                    fast_scored.append((score, key, text, json.loads(meta_json)))
                fast_scored.sort(key=lambda x: x[0], reverse=True)
                return [
                    {"key": k, "text": t, "score": round(s, 4), "metadata": m}
                    for s, k, t, m in fast_scored[:limit]
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

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        namespace: str = "default",
        limit: int = 5,
        alpha: float = 0.5,
        batch_size: int = _BATCH_SIZE,
    ) -> list[dict[str, Any]]:
        """Combine keyword (BM25) and semantic (cosine) scores into one ranking.

        Semantic candidates come from `search`; the same candidate set is then
        re-scored with Okapi BM25 against the raw `query` string. Both score
        vectors are min-max normalized to 0..1 and blended as
        ``final = alpha * semantic + (1 - alpha) * bm25``.
        """
        candidates = self.search(
            query_embedding,
            namespace=namespace,
            limit=max(limit * 3, 20),
            batch_size=batch_size,
        )
        if not candidates:
            return []
        texts = [c["text"] for c in candidates]
        bm25 = BM25Scorer().fit(texts)
        semantic_scores = _min_max_normalize([c["score"] for c in candidates])
        bm25_scores = _min_max_normalize([bm25.score(query, i) for i in range(len(texts))])
        combined: list[tuple[float, dict[str, Any], float, float]] = [
            (alpha * s + (1 - alpha) * b, c, s, b)
            for c, s, b in zip(candidates, semantic_scores, bm25_scores)
        ]
        combined.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "key": c["key"],
                "text": c["text"],
                "score": round(final, 4),
                "metadata": c["metadata"],
                "semantic_score": round(s, 4),
                "bm25_score": round(b, 4),
            }
            for final, c, s, b in combined[:limit]
        ]

    def count(self, namespace: str = "default") -> int:
        """Return the number of vectors stored in the given namespace."""
        row = self._get_conn().execute(
            "SELECT COUNT(*) FROM vectors WHERE namespace=?", (namespace,)
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

    @asyncify("hybrid_search")
    async def async_hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        namespace: str = "default",
        limit: int = 5,
        alpha: float = 0.5,
        batch_size: int = _BATCH_SIZE,
    ) -> list[dict[str, Any]]:
        return []


def create_vector_store(backend: str = "sqlite", db_path: str | None = None) -> VectorBackend:
    """Construct a vector store backend, falling back to sqlite when faiss is unavailable."""
    if backend == "faiss":
        try:
            from mcp_cli.services.vector_store_faiss import FaissVectorBackend
        except ImportError:
            pass
        else:
            if FaissVectorBackend.is_available():
                return FaissVectorBackend(db_path=db_path)
    return VectorStore(db_path=db_path)
