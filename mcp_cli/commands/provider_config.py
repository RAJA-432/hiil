from __future__ import annotations

_PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "default_model": "gpt-4o-mini"},
    "ollama": {"base_url": "http://localhost:11434/v1", "default_model": "gemma4:31b-cloud"},
    "opencode": {"base_url": "https://api.opencode.ai/v1", "default_model": "gpt-4o"},
}
