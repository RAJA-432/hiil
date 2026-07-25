"""
Configuration management for the application.
Supports loading from YAML and environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class ServerConfig:
    id: str
    script: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    command: str | None = None
    transport: str = "stdio"  # "stdio" or "sse"

    def resolve_launch(self) -> tuple[str, list[str]]:
        """Resolve (command, args) for subprocess launch, handling npx / uv / python."""
        if self.command:
            return self.command, [self.script, *self.args]
        if self.script.startswith("@"):
            return "npx", ["-y", self.script, *self.args]
        if os.getenv("USE_UV", "0") == "1":
            if self.script.endswith(".py") or "/" in self.script:
                return "uv", ["run", self.script, *self.args]
            return "uv", ["run", "python", "-m", self.script, *self.args]
        if self.script.endswith(".py") or "/" in self.script:
            return "python", [self.script, *self.args]
        return "python", ["-m", self.script, *self.args]

@dataclass
class Settings:
    """Resolved, validated runtime configuration."""
    provider: str
    model: str
    api_key: str
    base_url: str | None
    max_context_tokens: int = 200_000
    roots: list[str] = field(default_factory=lambda: ["."])

def load_settings(config_path: str = "config.yaml") -> tuple[Settings, list[ServerConfig]]:
    """
    Load settings and server configurations.
    Priority: YAML file -> Environment variables.
    """
    load_dotenv()

    # 1. Load from YAML
    yaml_config: dict[str, Any] = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f) or {}

    settings_yaml = yaml_config.get("settings", {})
    servers_yaml = yaml_config.get("servers", [])
    roots_yaml = yaml_config.get("roots", ["."])

    # 2. Resolve Settings (Env overrides YAML)
    provider = os.getenv("MODEL_PROVIDER", settings_yaml.get("provider", "openrouter")).lower()
    model = os.getenv("MODEL_NAME") or os.getenv("CLAUDE_MODEL") or settings_yaml.get("model")

    # Unified MODEL_API_KEY takes precedence; fall back to provider-specific legacy vars
    provider_key_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "opencode": "OPENCODE_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }
    from mcp_cli.services.credentials import load_api_key as _load_cred_key
    env_key = os.getenv("MODEL_API_KEY") or os.getenv(provider_key_map.get(provider, ""), "")
    yaml_key = settings_yaml.get("api_key", "")
    cred_key = _load_cred_key(provider) or ""
    api_key = env_key or cred_key or yaml_key or ""
    base_url = os.getenv("BASE_URL")

    if not model:
        raise ValueError("Model name must be provided in config.yaml or via MODEL_NAME env var")
    if api_key == "your-api-key-here":
        raise ValueError("Replace the placeholder 'your-api-key-here' in config.yaml with a real API key, or set MODEL_API_KEY in .env")
    if not api_key and provider != "ollama":
        raise ValueError("API Key must be provided in config.yaml or via MODEL_API_KEY env var")

    # Fallback base URLs by provider; YAML config only applies for unknown providers
    if not base_url:
        if provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        elif provider == "ollama":
            base_url = "http://localhost:11434/v1"
        else:
            base_url = settings_yaml.get("base_url")

    max_context_tokens = int(
        os.getenv("MAX_CONTEXT_TOKENS", settings_yaml.get("max_context_tokens", 200000))
    )

    settings = Settings(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_context_tokens=max_context_tokens,
        roots=[os.path.expanduser(r) for r in roots_yaml],
    )

    # 3. Resolve Servers
    servers = [ServerConfig(**s) for s in servers_yaml]

    _validate_config(settings, servers)
    return settings, servers


def _validate_config(settings: Settings, servers: list[ServerConfig]) -> None:
    pass
