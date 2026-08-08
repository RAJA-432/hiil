"""Airport/city catalog used by the Drishti Engine flight search tools.

Static, offline list of major world airports keyed by IATA code. Each entry
carries the display name, country and approximate geographic coordinates
used to compute great-circle flight distances.
"""

from __future__ import annotations

CITIES: dict[str, dict[str, object]] = {
    "DEL": {"name": "New Delhi", "country": "India", "lat": 28.6139, "lon": 77.2090},
    "BOM": {"name": "Mumbai", "country": "India", "lat": 19.0760, "lon": 72.8777},
    "BLR": {"name": "Bengaluru", "country": "India", "lat": 12.9716, "lon": 77.5946},
    "HYD": {"name": "Hyderabad", "country": "India", "lat": 17.3850, "lon": 78.4867},
    "MAA": {"name": "Chennai", "country": "India", "lat": 13.0827, "lon": 80.2707},
    "CCU": {"name": "Kolkata", "country": "India", "lat": 22.5726, "lon": 88.3639},
    "JFK": {"name": "New York", "country": "USA", "lat": 40.7128, "lon": -74.0060},
    "LAX": {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    "SFO": {"name": "San Francisco", "country": "USA", "lat": 37.7749, "lon": -122.4194},
    "ORD": {"name": "Chicago", "country": "USA", "lat": 41.8781, "lon": -87.6298},
    "LHR": {"name": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
    "CDG": {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
    "FRA": {"name": "Frankfurt", "country": "Germany", "lat": 50.1109, "lon": 8.6821},
    "AMS": {"name": "Amsterdam", "country": "Netherlands", "lat": 52.3676, "lon": 4.9041},
    "DXB": {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lon": 55.2708},
    "SIN": {"name": "Singapore", "country": "Singapore", "lat": 1.3521, "lon": 103.8198},
    "HKG": {"name": "Hong Kong", "country": "Hong Kong", "lat": 22.3193, "lon": 114.1694},
    "NRT": {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    "SYD": {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
    "BKK": {"name": "Bangkok", "country": "Thailand", "lat": 13.7563, "lon": 100.5018},
    "DOH": {"name": "Doha", "country": "Qatar", "lat": 25.2854, "lon": 51.5310},
    "IST": {"name": "Istanbul", "country": "Türkiye", "lat": 41.0082, "lon": 28.9784},
    "JNB": {"name": "Johannesburg", "country": "South Africa", "lat": -26.2041, "lon": 28.0473},
    "GRU": {"name": "São Paulo", "country": "Brazil", "lat": -23.5505, "lon": -46.6333},
    "PEK": {"name": "Beijing", "country": "China", "lat": 39.9042, "lon": 116.4074},
    "FCO": {"name": "Rome", "country": "Italy", "lat": 41.9028, "lon": 12.4964},
    "MAD": {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lon": -3.7038},
    "MEX": {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lon": -99.1332},
}
