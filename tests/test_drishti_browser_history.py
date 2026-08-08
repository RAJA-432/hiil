from __future__ import annotations

import json

import pytest

import drishti_engine.tools.browser_history as bh
from drishti_engine.data.browser_seed import DEFAULT_HISTORY
from drishti_engine.storage.store import JsonStore


@pytest.fixture
def history_store(tmp_path, monkeypatch):
    store = JsonStore(tmp_path / "browser_history.json", seed={"default": DEFAULT_HISTORY})
    monkeypatch.setattr(bh, "_history_store", store)
    monkeypatch.delenv("HIIL_USER_ID", raising=False)
    return store


async def test_search_finds_by_title(history_store):
    result = json.loads(await bh.browser_search("arxiv"))
    assert result["count"] >= 2
    assert any("arxiv" in r["title"].lower() for r in result["results"])


async def test_search_matches_url_and_domain(history_store):
    result = json.loads(await bh.browser_search("stackoverflow"))
    assert result["count"] >= 1
    assert result["results"][0]["domain"] == "stackoverflow.com"


async def test_search_orders_by_newest_last_visit(history_store):
    result = json.loads(await bh.browser_search("wikipedia"))
    visits = [r["last_visit"] for r in result["results"]]
    assert visits == sorted(visits, reverse=True)


async def test_search_respects_limit(history_store):
    result = json.loads(await bh.browser_search("a", limit=3))
    assert result["count"] <= 3


async def test_search_is_case_insensitive(history_store):
    result = json.loads(await bh.browser_search("GITHUB"))
    assert result["count"] >= 1
    assert result["results"][0]["domain"] == "github.com"


async def test_browser_add_records_visit_and_is_searchable(history_store):
    added = json.loads(await bh.browser_add(title="Example Docs", url="https://example.com/docs", tags="docs, howto"))
    assert added["status"] == "added"
    assert added["entry"]["domain"] == "example.com"
    assert added["entry"]["tags"] == ["docs", "howto"]

    result = json.loads(await bh.browser_search("example.com"))
    assert any(e["id"] == added["entry"]["id"] for e in result["results"])


async def test_browser_add_requires_title_and_url(history_store):
    with pytest.raises(ValueError, match="Title must not be empty."):
        await bh.browser_add(title="", url="https://example.com")
    with pytest.raises(ValueError, match="URL must not be empty."):
        await bh.browser_add(title="x", url="   ")
