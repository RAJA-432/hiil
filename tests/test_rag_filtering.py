from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from mcp_cli.services.rag import RagPipeline, estimated_tokens


class FakeClaude:
    def __init__(self) -> None:
        self.embed_calls = 0

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        self.embed_calls += 1
        return [0.1, 0.2, 0.3]


class RecordingVectorStore:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = results or []
        self._count = len(self._results)
        self.indexed: list[tuple[str, str, str, list[float], dict[str, Any]]] = []
        self.search_calls = 0

    def count(self, namespace: str = "default") -> int:
        return self._count

    async def async_search(
        self,
        query_embedding: list[float],
        namespace: str = "default",
        limit: int = 5,
        batch_size: int = 500,
    ) -> list[dict[str, Any]]:
        self.search_calls += 1
        return list(self._results[:limit])

    async def async_index(
        self,
        namespace: str,
        key: str,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.indexed.append((namespace, key, text, embedding, metadata or {}))
        self._count += 1

    async def async_list_keys(self, namespace: str = "default") -> list[str]:
        return [entry[1] for entry in self.indexed if entry[0] == namespace]

    async def async_delete(self, namespace: str, key: str) -> None:
        self.indexed = [entry for entry in self.indexed if not (entry[0] == namespace and entry[1] == key)]
        self._count = len(self.indexed)


def _result(key: str, text: str, score: float, metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {"key": key, "text": text, "score": score, "metadata": metadata}


class TestEstimatedTokens:
    def test_word_count_heuristic(self) -> None:
        assert estimated_tokens("") == 0
        assert estimated_tokens("one two three four") == 4

    def test_double_spaces_ignored(self) -> None:
        assert estimated_tokens("a   b\tc\n d") == 4


class TestRetrieveMetadataFiltering:
    def _store(self) -> RecordingVectorStore:
        return RecordingVectorStore([
            _result("a#chunk_0", "finance text", 0.9, {"domain": "finance", "filename": "a.txt"}),
            _result("b#chunk_0", "health text", 0.8, {"domain": "health", "filename": "b.txt"}),
            _result("c#chunk_0", "unlabeled text", 0.7, None),
        ])

    async def test_filter_returns_only_matching_metadata(self) -> None:
        rag = RagPipeline(FakeClaude(), self._store())
        out = await rag.retrieve("q", filter_metadata={"domain": "finance"})
        assert [r["key"] for r in out] == ["a#chunk_0"]

    async def test_filter_matches_all_pairs(self) -> None:
        rag = RagPipeline(FakeClaude(), self._store())
        out = await rag.retrieve("q", filter_metadata={"filename": "b.txt", "domain": "health"})
        assert [r["key"] for r in out] == ["b#chunk_0"]
        out = await rag.retrieve("q", filter_metadata={"filename": "b.txt", "domain": "finance"})
        assert out == []

    async def test_no_filter_returns_all(self) -> None:
        rag = RagPipeline(FakeClaude(), self._store())
        out = await rag.retrieve("q")
        assert [r["key"] for r in out] == ["a#chunk_0", "b#chunk_0", "c#chunk_0"]

    async def test_filter_combined_with_min_score(self) -> None:
        rag = RagPipeline(FakeClaude(), self._store())
        out = await rag.retrieve("q", min_score=0.85, filter_metadata={"domain": "health"})
        assert out == []

    async def test_retrieve_scoped_delegates_to_retrieve(self) -> None:
        rag = RagPipeline(FakeClaude(), self._store())
        out = await rag.retrieve_scoped("q", {"domain": "finance"})
        assert [r["key"] for r in out] == ["a#chunk_0"]


class TestIndexDocumentMetadata:
    async def test_caller_metadata_merged_into_chunks(self) -> None:
        store = RecordingVectorStore()
        rag = RagPipeline(FakeClaude(), store)
        await rag.index_document(
            b"hello world content",
            "doc.txt",
            metadata={"domain": "finance", "section": "quarterly"},
        )
        assert len(store.indexed) == 1
        _, key, text, _, meta = store.indexed[0]
        assert key == "doc.txt#chunk_0"
        assert text == "hello world content"
        assert meta["filename"] == "doc.txt"
        assert meta["source"] == "doc.txt"
        assert meta["chunk_index"] == 0
        assert meta["domain"] == "finance"
        assert meta["section"] == "quarterly"

    async def test_caller_metadata_overrides_defaults(self) -> None:
        store = RecordingVectorStore()
        rag = RagPipeline(FakeClaude(), store)
        await rag.index_document(b"some content", "doc.txt", metadata={"source": "custom-import"})
        _, _, _, _, meta = store.indexed[0]
        assert meta["source"] == "custom-import"

    async def test_index_without_metadata_keeps_defaults(self) -> None:
        store = RecordingVectorStore()
        rag = RagPipeline(FakeClaude(), store)
        await rag.index_document(b"some content", "doc.txt")
        _, _, _, _, meta = store.indexed[0]
        assert meta["source"] == "doc.txt"
        assert "domain" not in meta


class TestRetrieveCompressed:
    def _store_with(self, texts: list[tuple[str, float]]) -> RecordingVectorStore:
        return RecordingVectorStore([
            _result(f"c{i}", text, score, {"filename": "doc.txt"})
            for i, (text, score) in enumerate(texts)
        ])

    async def test_respects_max_tokens_budget(self) -> None:
        store = self._store_with([(" ".join(["word"] * 200), 0.9) for _ in range(4)])
        rag = RagPipeline(FakeClaude(), store)
        out = await rag.retrieve_compressed("q", max_tokens=500)
        assert out
        assert sum(r["estimated_tokens"] for r in out) <= 500
        assert all(r["compressed"] is False for r in out)
        assert [r["key"] for r in out] == ["c0", "c1"]

    async def test_under_budget_returns_everything(self) -> None:
        store = self._store_with([(" ".join(["word"] * 50), 0.9) for _ in range(3)])
        rag = RagPipeline(FakeClaude(), store)
        out = await rag.retrieve_compressed("q", max_tokens=500)
        assert [r["key"] for r in out] == ["c0", "c1", "c2"]
        assert sum(r["estimated_tokens"] for r in out) <= 500

    async def test_oversized_single_result_triggers_summarization(self) -> None:
        claude = FakeClaude()
        claude.chat = AsyncMock(return_value=SimpleNamespace(content="condensed summary here"))
        store = self._store_with([(" ".join(["word"] * 10000), 0.9)])
        rag = RagPipeline(claude, store)
        out = await rag.retrieve_compressed("q", max_tokens=500)
        assert len(out) == 1
        assert out[0]["compressed"] is True
        assert out[0]["text"] == "condensed summary here"
        assert out[0]["original_tokens"] == 10000
        assert claude.chat.called

    async def test_truncates_when_no_chat_method(self) -> None:
        rag = RagPipeline(FakeClaude(), self._store_with([(" ".join(["word"] * 1000), 0.9)]))
        out = await rag.retrieve_compressed("q", max_tokens=100)
        assert len(out) == 1
        assert out[0]["compressed"] is True
        assert estimated_tokens(out[0]["text"]) <= 100

    async def test_truncates_when_chat_fails(self) -> None:
        claude = FakeClaude()
        claude.chat = AsyncMock(side_effect=RuntimeError("boom"))
        rag = RagPipeline(claude, self._store_with([(" ".join(["word"] * 1000), 0.9)]))
        out = await rag.retrieve_compressed("q", max_tokens=100)
        assert len(out) == 1
        assert out[0]["compressed"] is True
        assert estimated_tokens(out[0]["text"]) <= 100

    async def test_returns_empty_for_empty_results(self) -> None:
        rag = RagPipeline(FakeClaude(), RecordingVectorStore([]))
        assert await rag.retrieve_compressed("q") == []
