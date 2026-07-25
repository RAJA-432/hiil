from unittest.mock import patch

import pytest

from mcp_cli.services.providers import get_available_providers, pick_provider


@patch("mcp_cli.services.providers.load_api_key", return_value="sk-key")
def test_get_available_providers_returns_list(mock_key):
    providers = get_available_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1


@patch("mcp_cli.services.providers.load_api_key", return_value="sk-key")
def test_get_available_providers_filters_by_key(mock_key):
    providers = get_available_providers()
    assert "openrouter" in providers


@patch("mcp_cli.services.providers.load_api_key", return_value=None)
def test_get_available_providers_empty_when_no_keys(mock_key):
    providers = get_available_providers()
    assert providers == []


@patch("mcp_cli.services.providers.load_api_key", return_value=None)
def test_pick_provider_defaults_to_ollama(mock_key):
    result = pick_provider("nonexistent")
    assert result == "ollama"


@patch("mcp_cli.services.providers.load_api_key", side_effect=lambda p: "sk-key" if p == "ollama" else None)
def test_pick_provider_preferred(mock_key):
    result = pick_provider("ollama")
    assert result == "ollama"


@patch("mcp_cli.services.providers.load_api_key", return_value=None)
def test_pick_provider_returns_string(mock_key):
    result = pick_provider()
    assert isinstance(result, str)
