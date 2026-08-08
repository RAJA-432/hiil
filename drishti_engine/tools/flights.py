"""Deterministic, offline mock flight search tools for the Drishti Engine server.

Provides ``search_flights`` and ``search_airports``. Results are generated
locally from a static airport catalog (``drishti_engine.data.cities``) using
hash-based determinism, so the same query always returns the same flights. No
API key or network access is required, mirroring the ``setu_bridge`` mock
conventions.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from typing import Annotated, Any

from pydantic import Field

from drishti_engine.data.cities import CITIES

_AIRLINES = (
    "IndiGo",
    "Air India",
    "Vistara",
    "Akasa Air",
    "SpiceJet",
    "Qatar Airways",
    "Emirates",
    "Singapore Airlines",
)

_CABIN_MULTIPLIER = {"economy": 1.0, "premium": 1.6, "business": 3.2, "first": 5.0}

_SORT_KEYS = ("price", "duration", "departure")

_EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _resolve(code: str) -> dict[str, Any]:
    """Normalize an IATA code or city name to a catalog entry."""
    query = code.strip().lower()
    if not query:
        raise ValueError("Airport or city must not be empty.")
    iata = query.upper() if query.upper() in CITIES else None
    if iata is None:
        for candidate, entry in CITIES.items():
            name = str(entry["name"]).lower()
            if query == name or query == name.split()[-1]:
                iata = candidate
                break
    if iata is None:
        raise ValueError(f"Unknown airport or city '{code}'")
    entry = CITIES[iata]
    return {
        "iata": iata,
        "name": str(entry["name"]),
        "country": str(entry["country"]),
        "lat": float(str(entry["lat"])),
        "lon": float(str(entry["lon"])),
    }


def _deterministic(seed_key: str, salt: int) -> int:
    """Stable pseudo-random integer derived from a seed string and salt."""
    return int(hashlib.sha256(f"{seed_key}|{salt}".encode()).hexdigest(), 16)


def _fare(distance_km: float, cabin: str, seed_key: str, idx: int) -> float:
    """Deterministic fare in USD: distance base with up to ±10% jitter."""
    base = distance_km * 0.09
    hashed = _deterministic(f"{seed_key}:fare", idx)
    jitter = 0.9 + (hashed % 200) / 1000.0
    price = base * _CABIN_MULTIPLIER[cabin] * jitter
    return round(max(price, 25.0), 2)


def _build_flight(
    origin: dict[str, Any],
    destination: dict[str, Any],
    distance_km: float,
    date: str,
    cabin: str,
    idx: int,
) -> dict[str, Any]:
    """Build one deterministic flight for the given route and index."""
    seed_key = f"{origin['iata']}:{destination['iata']}:{date}"
    hashed = _deterministic(seed_key, idx)
    airline = _AIRLINES[hashed % len(_AIRLINES)]
    flight = f"{airline[:2].upper()}{100 + (hashed % 900)}"
    departure = datetime.strptime(f"{date}T{6 + idx * 3:02d}:{(idx * 7) % 60:02d}", "%Y-%m-%dT%H:%M")
    duration_min = int(distance_km / 900.0 * 60) + 45
    arrival = departure + timedelta(minutes=duration_min)
    return {
        "flight": flight,
        "airline": airline,
        "origin": origin["iata"],
        "destination": destination["iata"],
        "departure": departure.isoformat(),
        "arrival": arrival.isoformat(),
        "duration_min": duration_min,
        "cabin": cabin,
        "price_usd": _fare(distance_km, cabin, seed_key, idx),
        "seats_left": 4 + (hashed % 60),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def search_flights(
    origin: str,
    destination: str,
    date: str,
    passengers: Annotated[int, Field(ge=1, le=9)] = 1,
    cabin: str = "economy",
    sort: str = "price",
    limit: Annotated[int, Field(ge=1, le=20)] = 10,
) -> str:
    """Search flights for a route and date (deterministic offline mock).

    Results are generated locally and are identical for the same inputs — no
    API key is required and no network call is made.

    Args:
        origin: IATA code (e.g. ``DEL``) or city name (e.g. ``Delhi``).
        destination: IATA code or city name.
        date: Travel date in ISO ``YYYY-MM-DD`` format.
        passengers: Number of passengers (1-9).
        cabin: Cabin class: economy, premium, business, or first.
        sort: Sort key: price, duration, or departure (ascending).
        limit: Maximum number of flights to return (1-20).
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date '{date}'. Expected ISO format YYYY-MM-DD (e.g. 2026-08-03).") from None
    origin_info = _resolve(origin)
    destination_info = _resolve(destination)
    if origin_info["iata"] == destination_info["iata"]:
        raise ValueError("Origin and destination must be different airports.")
    if cabin not in _CABIN_MULTIPLIER:
        raise ValueError(f"Invalid cabin '{cabin}'. Choose from {', '.join(_CABIN_MULTIPLIER)}.")
    if sort not in _SORT_KEYS:
        raise ValueError(f"Invalid sort '{sort}'. Choose from {', '.join(_SORT_KEYS)}.")

    distance_km = _haversine_km(
        origin_info["lat"],
        origin_info["lon"],
        destination_info["lat"],
        destination_info["lon"],
    )
    flights = [_build_flight(origin_info, destination_info, distance_km, date, cabin, idx) for idx in range(5)]
    if sort == "price":
        flights.sort(key=lambda f: f["price_usd"])
    elif sort == "duration":
        flights.sort(key=lambda f: f["duration_min"])
    else:
        flights.sort(key=lambda f: f["departure"])
    flights = flights[:limit]

    total = round(sum(f["price_usd"] * passengers for f in flights), 2)
    return json.dumps(
        {
            "origin": origin_info["iata"],
            "destination": destination_info["iata"],
            "date": date,
            "cabin": cabin,
            "passengers": passengers,
            "count": len(flights),
            "total_price_for_passengers": total,
            "currency": "USD",
            "flights": flights,
        },
        indent=2,
    )


async def search_airports(
    query: str = Field(..., min_length=1),
    limit: Annotated[int, Field(ge=1, le=25)] = 8,
) -> str:
    """Find airports/cities by IATA code or name fragment.

    Matches case-insensitively against the IATA code, city name, and country
    of the built-in catalog.

    Args:
        query: IATA code or name fragment (e.g. ``del`` or ``New York``).
        limit: Maximum number of results to return (1-25).
    """
    q = query.strip().lower()
    if not q:
        raise ValueError("Query must not be empty.")
    results: list[dict[str, Any]] = []
    for iata, entry in CITIES.items():
        name = str(entry["name"]).lower()
        country = str(entry["country"]).lower()
        if q in iata.lower() or q in name or q in country:
            results.append({"iata": iata, "name": str(entry["name"]), "country": str(entry["country"])})
    results = results[:limit]
    return json.dumps({"query": query, "count": len(results), "results": results}, indent=2)
