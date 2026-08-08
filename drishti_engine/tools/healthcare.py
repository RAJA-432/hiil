"""Healthcare-information search tools for the Drishti Engine server.

Provides a single async ``search_healthcare`` tool that returns curated,
general-education health entries (conditions, symptoms, medications) as
JSON. Educational only — results always carry a disclaimer and never a
diagnosis.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import Field

from drishti_engine.data.healthcare import HEALTHCARE_INDEX

_DISCLAIMER = (
    "This information is for general education only and is not a substitute for professional "
    "medical advice, diagnosis, or treatment. Always consult a qualified health provider with "
    "questions about a medical condition."
)

_VALID_CATEGORIES = frozenset({"conditions", "symptoms", "medications"})


def _matches(entry: dict, query: str) -> bool:
    """Return True when ``query`` matches an entry's name, category, or aliases."""
    q = query.casefold()
    if q in str(entry.get("name", "")).casefold():
        return True
    if q in str(entry.get("category", "")).casefold():
        return True
    return any(q in alias.casefold() for alias in entry.get("aliases", []))


async def search_healthcare(
    query: str = Field(description="Free-text query, e.g. 'headache' or 'cough with fever'", min_length=1),
    category: Annotated[str | None, Field(description="Optional filter: conditions, symptoms, or medications")] = None,
    limit: Annotated[int, Field(ge=1, le=20, description="Maximum number of results")] = 5,
) -> str:
    """Search the curated health-information index.

    Returns matching entries as JSON. Educational only — never a diagnosis;
    the response always includes a medical disclaimer.
    """
    if category is not None and category not in _VALID_CATEGORIES:
        raise ValueError(f"Unknown category '{category}'. Valid: conditions, symptoms, medications")

    q = query.strip()
    matches: list[dict[str, Any]] = [entry for entry in HEALTHCARE_INDEX if _matches(entry, q)]
    if category is not None:
        matches = [entry for entry in matches if entry["category"] == category]
    results = matches[:limit]

    return json.dumps(
        {
            "query": q,
            "count": len(results),
            "disclaimer": _DISCLAIMER,
            "results": results,
        },
        indent=2,
    )
