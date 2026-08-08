from __future__ import annotations

import json

import pytest

from drishti_engine.tools.healthcare import search_healthcare


async def test_search_finds_entry_and_disclaimer():
    result = json.loads(await search_healthcare("migraine"))
    assert result["count"] >= 1
    assert "disclaimer" in result
    assert any("migraine" in e["name"].lower() for e in result["results"])


async def test_category_filter():
    result = json.loads(await search_healthcare("ibuprofen", category="medications"))
    assert result["count"] >= 1
    assert all(e["category"] == "medications" for e in result["results"])


async def test_match_by_alias():
    result = json.loads(await search_healthcare("head hurts"))
    assert result["count"] >= 1
    assert result["results"][0]["name"].lower() in ("headache", "migraine")


async def test_limit_slicing():
    result = json.loads(await search_healthcare("a", limit=2))
    assert result["count"] <= 2


async def test_invalid_category_raises():
    with pytest.raises(ValueError, match="Unknown category 'vitamins'"):
        await search_healthcare("x", category="vitamins")
