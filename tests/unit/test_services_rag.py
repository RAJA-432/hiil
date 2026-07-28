from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_cli.services.rag import RagPipeline


@pytest.fixture
def mock_claude():
    c = MagicMock()
    c.embed = AsyncMock()
    return c


@pytest.fixture
def mock_vector_store():
    vs = MagicMock()
    vs.async_index = AsyncMock()
    vs.async_search = AsyncMock()
    vs.async_list_keys = AsyncMock()
    vs.async_delete = AsyncMock()
    return vs


@pytest.fixture
def rag(mock_claude, mock_vector_store):
    return RagPipeline(mock_claude, mock_vector_store)


class TestIndexDocument:
    async def test_indexes_plain_text(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.return_value = [0.1, 0.2, 0.3]
        result = await rag.index_document(
            b"hello world how are you doing today",
            "test.txt",
            chunk_size=100,
            chunk_overlap=0,
        )
        assert result["indexed"] == 1
        assert result["total_chunks"] == 1
        mock_vector_store.async_index.assert_awaited_once()

    async def test_handles_empty_text(self, rag):
        result = await rag.index_document(b"", "empty.txt")
        assert result["chunks"] == 0
        assert "error" in result

    async def test_indexes_multiple_chunks(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.return_value = [0.1, 0.2, 0.3]
        words = "word " * 200
        result = await rag.index_document(
            words.strip().encode(),
            "big.txt",
            chunk_size=20,
            chunk_overlap=2,
        )
        assert result["indexed"] >= 8
        assert result["total_chunks"] >= 8

    async def test_reports_embed_failures(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.side_effect = [[0.1, 0.2], []]
        words = "word " * 30
        result = await rag.index_document(
            words.strip().encode(),
            "partial.txt",
            chunk_size=15,
            chunk_overlap=0,
        )
        assert result["indexed"] == 1
        assert "errors" in result

    async def test_stores_text_in_index(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.return_value = [0.5, 0.5]
        await rag.index_document(b"some content here", "doc.txt", chunk_size=10, chunk_overlap=0)
        call_kwargs = mock_vector_store.async_index.call_args[1]
        assert "some content" in call_kwargs["text"]


class TestRetrieve:
    async def test_returns_results(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.return_value = [0.1, 0.2, 0.3]
        mock_vector_store.async_search.return_value = [
            {"key": "doc1", "text": "result text", "score": 0.95, "metadata": {"filename": "a.txt"}},
        ]
        results = await rag.retrieve("test query")
        assert len(results) == 1
        assert results[0]["key"] == "doc1"

    async def test_empty_on_no_embedding(self, rag, mock_claude):
        mock_claude.embed.return_value = []
        results = await rag.retrieve("test query")
        assert results == []

    async def test_applies_min_score_filter(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.return_value = [0.1, 0.2, 0.3]
        mock_vector_store.async_search.return_value = [
            {"key": "a", "text": "low", "score": 0.1, "metadata": {}},
            {"key": "b", "text": "high", "score": 0.9, "metadata": {}},
        ]
        results = await rag.retrieve("query", min_score=0.5)
        assert len(results) == 1
        assert results[0]["key"] == "b"

    async def test_respects_top_k(self, rag, mock_claude, mock_vector_store):
        mock_claude.embed.return_value = [0.1, 0.2, 0.3]
        mock_vector_store.async_search.return_value = [
            {"key": f"doc{i}", "text": "x", "score": 0.9, "metadata": {}}
            for i in range(10)
        ]
        results = await rag.retrieve("query", top_k=3)
        assert len(results) == 10


class TestFormatContext:
    def test_empty_results_returns_empty_string(self, rag):
        assert rag.format_context([]) == ""

    def test_formats_single_result(self, rag):
        results = [
            {"key": "doc1", "text": "some text", "score": 0.95, "metadata": {"filename": "a.txt"}},
        ]
        out = rag.format_context(results)
        assert "a.txt" in out
        assert "0.950" in out
        assert "some text" in out

    def test_formats_multiple_results(self, rag):
        results = [
            {"key": "d1", "text": "t1", "score": 0.9, "metadata": {"filename": "a.txt"}},
            {"key": "d2", "text": "t2", "score": 0.8, "metadata": {"filename": "b.txt"}},
        ]
        out = rag.format_context(results)
        assert "[1]" in out
        assert "[2]" in out


class TestDeleteDocument:
    async def test_deletes_matching_keys(self, rag, mock_vector_store):
        mock_vector_store.async_list_keys.return_value = [
            "doc.txt#chunk_0", "doc.txt#chunk_1", "other.txt#chunk_0",
        ]
        mock_vector_store.async_delete.return_value = True
        deleted = await rag.delete_document("doc.txt")
        assert deleted == 2
        assert mock_vector_store.async_delete.await_count == 2

    async def test_returns_zero_for_no_matches(self, rag, mock_vector_store):
        mock_vector_store.async_list_keys.return_value = ["other.txt#chunk_0"]
        deleted = await rag.delete_document("nonexistent.txt")
        assert deleted == 0
