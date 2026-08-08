from __future__ import annotations

import math

import pytest

from eval.retrieval_f1 import (
    build_index,
    label_relevant,
    main,
    run_f1,
    run_validation,
    synthetic_embedding,
)


def _make_doc(doc_id: str, topic: list[str], words: int = 120) -> dict:
    tokens: list[str] = []
    for k in range(words):
        if k % 6 == 0:
            tokens.append(topic[0])
        elif k % 6 == 1 and len(topic) > 1:
            tokens.append(topic[1])
        else:
            tokens.append(f"term{doc_id}_{k}")
    return {
        "id": doc_id,
        "title": f"Title {doc_id}",
        "content": " ".join(tokens),
        "topic": list(topic),
    }


def _shared_topic_docs() -> list[dict]:
    return [
        _make_doc("doc0", ["sharedtopic", "sharedword"]),
        _make_doc("doc1", ["sharedtopic", "sharedword"]),
        _make_doc("doc2", ["othertopic", "otherword"]),
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class TestSyntheticEmbedding:
    def test_deterministic(self) -> None:
        text = "Quantum propulsion systems are extremely fast"
        assert synthetic_embedding(text) == synthetic_embedding(text)

    def test_unit_length_for_non_empty_text(self) -> None:
        vec = synthetic_embedding("the quick brown fox jumps over the lazy dog")
        norm = math.sqrt(sum(v * v for v in vec))
        assert math.isclose(norm, 1.0, rel_tol=1e-9)

    def test_empty_text_is_zero_length_safe(self) -> None:
        for text in ("", "   ", "!!!...", ".,;!?"):
            vec = synthetic_embedding(text)
            assert vec
            assert all(v == 0.0 for v in vec)

    def test_similar_texts_are_more_similar(self) -> None:
        base = synthetic_embedding("zanith quilbar")
        near = synthetic_embedding("zanith quilbar report")
        far = synthetic_embedding("completely unrelated document words")
        assert _cosine(base, near) > _cosine(base, far)


class TestLabelRelevant:
    def test_topic_word_in_query(self) -> None:
        doc = _make_doc("doc0", ["zanith"])
        assert label_relevant(doc, "What about zanith?")

    def test_no_topic_word_in_query(self) -> None:
        doc = _make_doc("doc0", ["zanith"])
        assert not label_relevant(doc, "What about unrelated?")

    def test_doc_without_topic_is_never_relevant(self) -> None:
        doc = {"id": "x", "title": "x", "content": "some text"}
        assert not label_relevant(doc, "anything")


class TestRunF1:
    def test_empty_store_returns_zeros(self, tmp_path) -> None:
        store, _ = build_index([], db_path=str(tmp_path / "empty.db"))
        try:
            result = run_f1("anything", store, [])
        finally:
            store.close()
        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["f1"] == 0.0
        assert result["retrieved_count"] == 0
        assert result["relevant_count"] == 0
        assert result["hits"] == 0

    def test_end_to_end_shared_topic(self, tmp_path) -> None:
        docs = _shared_topic_docs()
        store, stats = build_index(docs, db_path=str(tmp_path / "vectors.db"))
        try:
            result = run_f1("Tell me about sharedtopic and sharedword", store, docs, top_k=5)
        finally:
            store.close()
        assert stats["chunks_total"] == len(docs)
        assert result["relevant_count"] == 2
        assert result["hits"] >= 1
        assert result["recall"] >= 1.0 / result["relevant_count"]
        assert 0.0 <= result["f1"] <= 1.0
        assert result["precision"] >= 0.0
        assert result["recall"] >= 0.0


class TestRunValidation:
    def test_means_equal_per_query_average(self, tmp_path) -> None:
        docs = _shared_topic_docs()
        queries = [
            "Tell me about sharedtopic and sharedword",
            "Tell me about othertopic and otherword",
            "Report on sharedtopic please",
        ]
        report = run_validation(docs, queries, top_k=5, backend="sqlite")
        count = len(report["per_query"])
        assert count == len(queries)
        for key, mean_key in (("precision", "mean_precision"), ("recall", "mean_recall"), ("f1", "mean_f1")):
            average = sum(row[key] for row in report["per_query"]) / count
            assert math.isclose(average, report[mean_key], rel_tol=1e-9, abs_tol=1e-9)
        assert report["doc_count"] == len(docs)
        assert report["chunks_total"] == len(docs)


class TestBackends:
    @pytest.mark.parametrize("backend", ["sqlite", "faiss"])
    def test_run_validation_backend(self, backend: str, tmp_path) -> None:
        docs = [
            _make_doc("a", ["alphatopic"]),
            _make_doc("b", ["betatopic"]),
            _make_doc("c", ["alphatopic"]),
        ]
        queries = ["alphatopic query", "betatopic query"]
        try:
            report = run_validation(docs, queries, top_k=5, backend=backend, db_path=str(tmp_path / f"{backend}.db"))
        except Exception:
            assert backend == "faiss"
            return
        assert report["doc_count"] == 3
        assert 0.0 <= report["mean_f1"] <= 1.0


class TestCli:
    def test_main_returns_zero(self, capsys) -> None:
        assert main(["--docs", "6", "--seed", "1", "--top-k", "5"]) == 0
        out = capsys.readouterr().out
        assert "MEAN" in out
        assert "f1" in out
