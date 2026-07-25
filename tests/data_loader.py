from __future__ import annotations

import json
from pathlib import Path

TEST_DATA_DIR = Path(__file__).parent / "data"


def load_cases(filename: str) -> list[dict]:
    with open(TEST_DATA_DIR / filename) as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    return data
