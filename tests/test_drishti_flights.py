from __future__ import annotations

import json

import pytest

from drishti_engine.tools.flights import search_airports, search_flights


async def test_search_flights_is_deterministic():
    a = json.loads(await search_flights("DEL", "BOM", "2026-08-20"))
    b = json.loads(await search_flights("DEL", "BOM", "2026-08-20"))
    assert a == b
    assert a["origin"] == "DEL"
    assert a["destination"] == "BOM"
    assert a["currency"] == "USD"
    assert a["count"] == 5
    assert all(f["cabin"] == "economy" for f in a["flights"])


async def test_search_flights_sorts_by_price():
    result = json.loads(await search_flights("DEL", "BOM", "2026-08-20", sort="price"))
    prices = [f["price_usd"] for f in result["flights"]]
    assert prices == sorted(prices)


async def test_search_flights_sorts_by_departure():
    result = json.loads(await search_flights("DEL", "BOM", "2026-08-20", sort="departure"))
    departures = [f["departure"] for f in result["flights"]]
    assert departures == sorted(departures)


async def test_search_flights_accepts_city_names():
    result = json.loads(await search_flights("Delhi", "Mumbai", "2026-08-20"))
    assert result["origin"] == "DEL"
    assert result["destination"] == "BOM"


async def test_passengers_scales_total():
    one = json.loads(await search_flights("DEL", "BOM", "2026-08-20", passengers=1))
    two = json.loads(await search_flights("DEL", "BOM", "2026-08-20", passengers=2))
    assert two["total_price_for_passengers"] == round(one["total_price_for_passengers"] * 2, 2)


async def test_search_flights_validation():
    with pytest.raises(ValueError, match="Invalid date '2026/08/20'"):
        await search_flights("DEL", "BOM", "2026/08/20")
    with pytest.raises(ValueError, match="Unknown airport or city 'ATLANTIS'"):
        await search_flights("DEL", "ATLANTIS", "2026-08-20")
    with pytest.raises(ValueError, match="must be different"):
        await search_flights("DEL", "Delhi", "2026-08-20")
    with pytest.raises(ValueError, match="Invalid cabin 'yacht'"):
        await search_flights("DEL", "BOM", "2026-08-20", cabin="yacht")
    with pytest.raises(ValueError, match="Invalid sort 'random'"):
        await search_flights("DEL", "BOM", "2026-08-20", sort="random")


async def test_search_airports_by_code_name_and_country():
    by_code = json.loads(await search_airports("del"))
    assert any(r["iata"] == "DEL" for r in by_code["results"])

    by_name = json.loads(await search_airports("New York"))
    assert any(r["iata"] == "JFK" for r in by_name["results"])

    by_country = json.loads(await search_airports("india"))
    assert by_country["count"] >= 1
    assert all(r["country"] == "India" for r in by_country["results"])


async def test_search_airports_empty_query_raises():
    with pytest.raises(ValueError, match="Query must not be empty."):
        await search_airports("   ")
