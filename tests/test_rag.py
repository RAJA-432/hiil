from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from mcp_cli.services.claude import LLMClient
from mcp_cli.services.rag import RagPipeline


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self._payload = payload or {}
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClaude:
    def __init__(self, embedding: tuple[float, ...] = (0.1, 0.2, 0.3), delay: float = 0.0) -> None:
        self.embed_calls = 0
        self._embedding = list(embedding)
        self._delay = delay

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        self.embed_calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        return list(self._embedding)


class FakeVectorStore:
    def __init__(self, count: int = 0) -> None:
        self._count = count
        self.count_calls = 0
        self.search_calls = 0

    def count(self, namespace: str = "default") -> int:
        self.count_calls += 1
        return self._count

    async def async_search(self, query_embedding: list[float], namespace: str = "default", limit: int = 5, batch_size: int = 500) -> list[dict[str, Any]]:
        self.search_calls += 1
        return []

    async def async_index(self, namespace: str, key: str, text: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        self._count += 1


class TestEmptyKbFastPath:
    async def test_retrieve_returns_empty_without_embedding(self) -> None:
        store = FakeVectorStore(count=0)
        claude = FakeClaude()
        rag = RagPipeline(claude, store)
        assert await rag.retrieve("some query") == []
        assert claude.embed_calls == 0
        assert store.search_calls == 0

    async def test_empty_status_is_cached(self) -> None:
        store = FakeVectorStore(count=0)
        rag = RagPipeline(FakeClaude(), store)
        await rag.retrieve("q1")
        await rag.retrieve("q2")
        assert store.count_calls == 1

    async def test_retrieve_after_indexing_rechecks_emptiness(self) -> None:
        store = FakeVectorStore(count=0)
        claude = FakeClaude()
        rag = RagPipeline(claude, store)
        await rag.retrieve("q")
        assert claude.embed_calls == 0
        await rag.index_document(b"hello world content", "doc.txt")
        await rag.retrieve("q")
        assert claude.embed_calls == 2
        assert store.search_calls == 1

    async def test_retrieve_on_populated_store_embeds_and_searches(self) -> None:
        store = FakeVectorStore(count=5)
        claude = FakeClaude()
        rag = RagPipeline(claude, store)
        assert await rag.retrieve("some query") == []
        assert claude.embed_calls == 1
        assert store.search_calls == 1


class TestIndexSingleFlight:
    async def test_concurrent_index_calls_run_single_execution(self) -> None:
        store = FakeVectorStore()
        claude = FakeClaude(delay=0.01)
        rag = RagPipeline(claude, store)
        content = b"word " * 600
        r1, r2 = await asyncio.gather(
            rag.index_document(content, "doc.txt", chunk_size=256, chunk_overlap=64),
            rag.index_document(content, "doc.txt", chunk_size=256, chunk_overlap=64),
        )
        assert r1 == r2
        assert r1["indexed"] == 3
        assert claude.embed_calls == 3

    async def test_distinct_files_index_independently(self) -> None:
        store = FakeVectorStore()
        claude = FakeClaude(delay=0.01)
        rag = RagPipeline(claude, store)
        content = b"hello world content"
        r1, r2 = await asyncio.gather(
            rag.index_document(content, "a.txt"),
            rag.index_document(content, "b.txt"),
        )
        assert r1["indexed"] == 1
        assert r2["indexed"] == 1
        assert claude.embed_calls == 2


class TestEmbedCache:
    def _client(self) -> tuple[LLMClient, dict[str, int]]:
        client = LLMClient(provider="openrouter", model="gpt-4", api_key="test-key")
        calls: dict[str, int] = {"count": 0}

        async def fake_post(url: str, **kwargs: Any) -> FakeResponse:
            calls["count"] += 1
            return FakeResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

        client._http_client = SimpleNamespace(post=fake_post)
        return client, calls

    async def test_repeated_embed_text_hits_cache(self) -> None:
        client, calls = self._client()
        first = await client.embed("hello world")
        second = await client.embed("hello world")
        assert first == [0.1, 0.2, 0.3]
        assert second == first
        assert calls["count"] == 1

    async def test_failure_is_not_cached(self) -> None:
        client = LLMClient(provider="openrouter", model="gpt-4", api_key="test-key")
        calls: dict[str, int] = {"count": 0}

        async def fake_post(url: str, **kwargs: Any) -> FakeResponse:
            calls["count"] += 1
            return FakeResponse(error=RuntimeError("boom"))

        client._http_client = SimpleNamespace(post=fake_post)
        assert await client.embed("hello") == []
        assert await client.embed("hello") == []
        assert calls["count"] == 2

    async def test_cache_is_bounded_lru(self) -> None:
        client, calls = self._client()
        with patch("mcp_cli.services.claude._EMBED_CACHE_MAXSIZE", 2):
            for text in ("a", "b", "c"):
                await client.embed(text)
            assert calls["count"] == 3
            await client.embed("a")
            assert calls["count"] == 4
            await client.embed("c")
            assert calls["count"] == 4
