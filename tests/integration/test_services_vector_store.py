import math

import pytest

from mcp_cli.services.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    db = str(tmp_path / "vectors.db")
    vs = VectorStore(db)
    yield vs
    vs.close()


def test_index_and_search(store):
    store.index("default", "doc1", "hello world", [1.0, 0.0, 0.0])
    store.index("default", "doc2", "goodbye world", [0.0, 1.0, 0.0])
    results = store.search([1.0, 0.0, 0.0], limit=5)
    assert len(results) == 2
    assert results[0]["key"] == "doc1"
    assert results[0]["score"] > 0.99


def test_search_empty(store):
    results = store.search([1.0, 0.0, 0.0])
    assert results == []


def test_index_overwrites(store):
    store.index("default", "dup", "first", [1.0, 0.0])
    store.index("default", "dup", "second", [0.0, 1.0])
    results = store.search([0.0, 1.0])
    assert results[0]["text"] == "second"


def test_delete(store):
    store.index("ns", "k1", "text1", [1.0, 0.0])
    assert store.count("ns") == 1
    assert store.delete("ns", "k1") is True
    assert store.count("ns") == 0


def test_delete_nonexistent(store):
    assert store.delete("ns", "ghost") is False


def test_delete_namespace(store):
    store.index("a", "x", "t1", [1.0])
    store.index("a", "y", "t2", [1.0])
    store.index("b", "z", "t3", [1.0])
    assert store.delete_namespace("a") == 2
    assert store.count("a") == 0
    assert store.count("b") == 1


def test_list_keys(store):
    store.index("ns", "k1", "t", [1.0])
    store.index("ns", "k2", "t", [1.0])
    keys = store.list_keys("ns")
    assert keys == ["k1", "k2"]


def test_list_keys_empty(store):
    assert store.list_keys("empty") == []


def test_count(store):
    store.index("ns", "a", "t", [1.0])
    store.index("ns", "b", "t", [1.0])
    assert store.count("ns") == 2


def test_count_empty(store):
    assert store.count("empty") == 0


def test_cosine_similarity_identical():
    vs = VectorStore(":memory:")
    assert vs._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    vs = VectorStore(":memory:")
    assert vs._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite():
    vs = VectorStore(":memory:")
    assert vs._cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_zero():
    vs = VectorStore(":memory:")
    assert vs._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosine_similarity_partial():
    vs = VectorStore(":memory:")
    a = [1.0, 1.0, 0.0]
    b = [1.0, 0.0, 0.0]
    expected = 1.0 / math.sqrt(2)
    assert vs._cosine_similarity(a, b) == pytest.approx(expected)


def test_search_returns_metadata(store):
    store.index("ns", "doc", "text", [1.0, 0.0], metadata={"source": "test"})
    results = store.search([1.0, 0.0], namespace="ns")
    assert results[0]["metadata"]["source"] == "test"


def test_search_ordered_by_score(store):
    store.index("ns", "best", "best match", [1.0, 0.0, 0.0])
    store.index("ns", "med", "medium match", [0.8, 0.0, 0.0])
    store.index("ns", "worst", "worst match", [0.2, 0.0, 0.0])
    results = store.search([1.0, 0.0, 0.0], namespace="ns", limit=3)
    assert results[0]["key"] == "best"
    assert results[1]["key"] == "med"
    assert results[2]["key"] == "worst"


def test_search_limit(store):
    for i in range(10):
        store.index("ns", f"k{i}", f"text{i}", [1.0])
    results = store.search([1.0], namespace="ns", limit=3)
    assert len(results) == 3


def test_search_different_namespace(store):
    store.index("ns1", "k", "text", [1.0, 0.0])
    store.index("ns2", "k", "other", [0.0, 1.0])
    results = store.search([1.0, 0.0], namespace="ns2")
    assert len(results) == 1
    assert results[0]["text"] == "other"


def test_index_with_metadata(store):
    store.index("ns", "k", "text", [1.0], metadata={"type": "note", "created": "2024"})
    results = store.search([1.0], namespace="ns")
    assert results[0]["metadata"]["type"] == "note"


def test_db_path_default():
    vs = VectorStore()
    assert ".hiil" in vs.db_path
    assert vs.db_path.endswith("vectors.db")
    vs.close()


def test_multiple_namespaces_independent(store):
    store.index("a", "k1", "alpha", [1.0, 0.0])
    store.index("b", "k2", "beta", [0.0, 1.0])
    assert store.count("a") == 1
    assert store.count("b") == 1
    assert store.list_keys("a") == ["k1"]
    assert store.list_keys("b") == ["k2"]
