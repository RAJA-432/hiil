from __future__ import annotations

import builtins
import sys

import pytest

from mcp_cli.services.vector_store import VectorStore, create_vector_store

_DOCS = [
    ("k1", "hello world", [1.0, 0.0, 0.0], {"filename": "a.txt"}),
    ("k2", "vector world", [0.8, 0.6, 0.0], {"filename": "b.txt"}),
    ("k3", "another document", [0.0, 1.0, 0.0], {"filename": "c.txt"}),
]


def _seed(store) -> None:
    for key, text, emb, meta in _DOCS:
        store.index("ns", key, text, emb, meta)


class TestSqliteBackendConformance:
    def test_interface_conformance(self, tmp_path) -> None:
        store = create_vector_store("sqlite", db_path=str(tmp_path / "vectors.db"))
        assert isinstance(store, VectorStore)
        _seed(store)
        assert store.count("ns") == 3
        assert store.count("other") == 0
        results = store.search([1.0, 0.0, 0.0], namespace="ns", limit=2)
        assert [r["key"] for r in results] == ["k1", "k2"]
        assert results[0]["text"] == "hello world"
        assert results[0]["score"] == 1.0
        assert results[0]["metadata"] == {"filename": "a.txt"}
        assert store.list_keys("ns") == ["k1", "k2", "k3"]
        page = store.search_page([1.0, 0.0, 0.0], namespace="ns", offset=0, limit=2)
        assert [r["key"] for r in page] == ["k1", "k2"]
        assert store.delete("ns", "k1") is True
        assert store.delete("ns", "k1") is False
        assert store.count("ns") == 2
        assert store.delete_namespace("ns") == 2
        assert store.count("ns") == 0
        store.close()

    async def test_async_wrappers(self, tmp_path) -> None:
        store = create_vector_store("sqlite", db_path=str(tmp_path / "vectors.db"))
        await store.async_index("ns", "k1", "hello world", [1.0, 0.0, 0.0], {"filename": "a.txt"})
        assert store.count("ns") == 1
        results = await store.async_search([1.0, 0.0, 0.0], namespace="ns")
        assert [r["key"] for r in results] == ["k1"]
        assert await store.async_list_keys("ns") == ["k1"]
        assert await store.async_delete("ns", "k1") is True
        assert store.count("ns") == 0
        store.close()


class TestFaissBackendConformance:
    def test_interface_conformance(self, tmp_path) -> None:
        pytest.importorskip("faiss")
        from mcp_cli.services.vector_store_faiss import FaissVectorBackend

        store = create_vector_store("faiss", db_path=str(tmp_path / "vectors.db"))
        assert isinstance(store, FaissVectorBackend)
        _seed(store)
        assert store.count("ns") == 3
        results = store.search([1.0, 0.0, 0.0], namespace="ns", limit=2)
        assert [r["key"] for r in results] == ["k1", "k2"]
        assert results[0]["text"] == "hello world"
        assert results[0]["score"] == 1.0
        assert results[0]["metadata"] == {"filename": "a.txt"}
        assert store.list_keys("ns") == ["k1", "k2", "k3"]
        page = store.search_page([1.0, 0.0, 0.0], namespace="ns", offset=0, limit=2)
        assert [r["key"] for r in page] == ["k1", "k2"]
        assert store.delete("ns", "k1") is True
        assert store.count("ns") == 2
        assert store.delete_namespace("ns") == 2
        assert store.count("ns") == 0
        store.close()


class TestBackendSelection:
    def test_default_is_sqlite(self, tmp_path) -> None:
        store = create_vector_store(db_path=str(tmp_path / "vectors.db"))
        assert isinstance(store, VectorStore)
        store.close()

    def test_faiss_falls_back_to_sqlite_when_unavailable(self, tmp_path, monkeypatch) -> None:
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "faiss":
                raise ImportError("faiss is not installed")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        monkeypatch.delitem(sys.modules, "faiss", raising=False)
        store = create_vector_store("faiss", db_path=str(tmp_path / "vectors.db"))
        assert isinstance(store, VectorStore)
        store.close()
