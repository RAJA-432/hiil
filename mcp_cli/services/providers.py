"""
Support for selecting among multiple model providers.
"""

from __future__ import annotations

import os

from .credentials import load_api_key


def get_available_providers() -> list[str]:
    """Return a prioritized list of provider names that have API keys configured."""
    providers = os.getenv("MODEL_PROVIDERS", "openrouter,opencode,ollama").split(",")
    available: list[str] = []
    for p in providers:
        p = p.strip().lower()
        if load_api_key(p):
            available.append(p)
    return available


def pick_provider(preferred: str | None = None) -> str:
    """Return a provider suitable for use, preferring the one given if available."""
    if preferred:
        pk = load_api_key(preferred)
        if pk:
            return preferred
    for p in get_available_providers():
        return p
    # Default to ollama if nothing is configured – it requires no key.
    return "ollama"
