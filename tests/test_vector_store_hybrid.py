from __future__ import annotations

import math

import pytest

import mcp_cli.services.vector_store as vs
from mcp_cli.services.vector_store import BM25Scorer, VectorStore, create_vector_store

_HYBRID_DOCS = [
    ("rare", "the quasar anomaly pulse is extremely rare", [1.0, 0.0], {"tag": "rare"}),
    ("mid", "another generic unrelated paragraph of filler words", [0.5, 0.5], {"tag": "mid"}),
    ("common", "a totally unrelated everyday discussion about weather", [0.0, 1.0], {"tag": "common"}),
]


def _seed_docs(store, namespace: str = "ns", count: int = 3, offset: int = 0) -> None:
    for i in range(count):
        angle = math.radians((i + offset) * 7)
        store.index(namespace, f"k{i + offset}", f"doc {i + offset} text", [math.cos(angle), math.sin(angle)], {"idx": i + offset})


def _seed_hybrid_docs(store, namespace: str = "ns") -> None:
    for key, text, emb, meta in _HYBRID_DOCS:
        store.index(namespace, key, text, emb, meta)


class TestPersistenceRoundTrip:
    def test_roundtrip_sqlite(self, tmp_path) -> None:
        db = str(tmp_path / "vectors.db")
        store = VectorStore(db_path=db)
        _seed_docs(store, count=10)
        expected_count = store.count("ns")
        expected_keys = store.list_keys("ns")
        expected_search = [r["key"] for r in store.search([1.0, 0.0], namespace="ns", limit=5)]
        store.close()

        reopened = VectorStore(db_path=db)
        assert reopened.count("ns") == expected_count
        assert reopened.list_keys("ns") == expected_keys
        assert [r["key"] for r in reopened.search([1.0, 0.0], namespace="ns", limit=5)] == expected_search
        reopened.close()

    def test_roundtrip_faiss(self, tmp_path) -> None:
        try:
            from mcp_cli.services.vector_store_faiss import FaissVectorBackend
        except ImportError:
            FaissVectorBackend = None
        if FaissVectorBackend is None or not FaissVectorBackend.is_available():
            pytest.skip("faiss backend not available")
        db = str(tmp_path / "vectors.db")
        store = create_vector_store("faiss", db_path=db)
        assert isinstance(store, FaissVectorBackend)
        _seed_docs(store, count=10)
        expected_count = store.count("ns")
        expected_keys = store.list_keys("ns")
        expected_search = [r["key"] for r in store.search([1.0, 0.0], namespace="ns", limit=5)]
        store.close()

        reopened = create_vector_store("faiss", db_path=db)
        assert isinstance(reopened, FaissVectorBackend)
        assert reopened.count("ns") == expected_count
        assert reopened.list_keys("ns") == expected_keys
        assert [r["key"] for r in reopened.search([1.0, 0.0], namespace="ns", limit=5)] == expected_search
        reopened.close()


class TestIvfTuning:
    def test_ivf_stats_returns_expected_keys_and_count(self, tmp_path) -> None:
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_docs(store, count=3)
        stats = store.ivf_stats("ns")
        assert set(stats) == {"count", "n_clusters", "n_probe", "has_index"}
        assert stats["count"] == 3
        assert stats["n_clusters"] == vs._IVF_N_CLUSTERS
        assert stats["n_probe"] == vs._IVF_N_PROBE
        assert stats["has_index"] is False
        store.close()

    def test_tune_picks_reasonable_clusters_for_small_corpus(self, tmp_path) -> None:
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_docs(store, count=100)
        stats = store.tune("ns")
        expected_clusters = min(vs._IVF_N_CLUSTERS, max(1, round(math.sqrt(100))))
        assert stats["count"] == 100
        assert stats["n_clusters"] == expected_clusters == 10
        assert stats["n_probe"] == max(1, min(expected_clusters, int(expected_clusters * 0.1))) == 1
        assert stats["has_index"] is True
        store.close()

    def test_tune_keeps_defaults_for_tiny_corpus(self, tmp_path) -> None:
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_docs(store, count=3)
        stats = store.tune("ns")
        assert stats["n_clusters"] == vs._IVF_N_CLUSTERS
        assert stats["n_probe"] == vs._IVF_N_PROBE
        assert stats["has_index"] is False
        store.close()


class TestBM25Scorer:
    def test_ranks_exact_keyword_doc_above_unrelated(self) -> None:
        docs = [
            "the quick brown fox jumps over the lazy dog",
            "python is a programming language",
            "rocket engines need strong turbopumps",
            "the rare quasar emits jets of plasma",
        ]
        scorer = BM25Scorer().fit(docs)
        assert scorer.score("quasar", 3) > 0.0
        ranked = scorer.rank("quasar", docs)
        assert ranked[0][1] == 3
        assert scorer.score("quasar", 3) > scorer.score("quasar", 0)
        assert scorer.score("quasar", 3) > scorer.score("quasar", 1)
        assert scorer.score("quasar", 3) > scorer.score("quasar", 2)


class TestHybridSearch:
    def test_returns_limit_results_with_score_keys(self, tmp_path) -> None:
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_hybrid_docs(store)
        results = store.hybrid_search("quasar", [1.0, 0.0], namespace="ns", limit=2, alpha=0.2)
        assert len(results) == 2
        for r in results:
            assert {"key", "text", "score", "metadata", "semantic_score", "bm25_score"} <= set(r)
        store.close()

    def test_rare_keyword_doc_boosted_when_alpha_favors_keyword(self, tmp_path) -> None:
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_hybrid_docs(store)
        results = store.hybrid_search("quasar", [1.0, 0.0], namespace="ns", limit=2, alpha=0.2)
        assert results[0]["key"] == "rare"
        assert results[0]["semantic_score"] == 1.0
        assert results[0]["bm25_score"] == 1.0
        assert results[1]["key"] == "mid"
        assert results[1]["bm25_score"] == 0.0
        store.close()

    def test_works_without_numpy(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(vs, "_HAS_NUMPY", False)
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_hybrid_docs(store)
        results = store.hybrid_search("quasar", [1.0, 0.0], namespace="ns", limit=2, alpha=0.2)
        assert results[0]["key"] == "rare"
        assert results[0]["semantic_score"] == 1.0
        store.close()

    async def test_async_hybrid_search_returns_same_shape(self, tmp_path) -> None:
        store = VectorStore(db_path=str(tmp_path / "vectors.db"))
        _seed_hybrid_docs(store)
        results = await store.async_hybrid_search("quasar", [1.0, 0.0], namespace="ns", limit=2, alpha=0.2)
        assert len(results) == 2
        assert results[0]["key"] == "rare"
        assert {"semantic_score", "bm25_score"} <= set(results[0])
        store.close()
