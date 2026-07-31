from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from mcp_cli.services.chat import CliChat
from mcp_cli.services.claude import LLMClient


def _ollama_client(model: str = "gemma4:31b-cloud") -> LLMClient:
    return LLMClient(
        provider="ollama",
        model=model,
        api_key="",
        base_url="http://localhost:11434/v1",
    )


def _install_fake_get(client: LLMClient, fake_get: Any) -> None:
    cast(Any, client)._http_client = SimpleNamespace(get=fake_get)


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self._payload = payload or {}
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> dict[str, Any]:
        return self._payload


class TestModelCapabilities:
    async def test_vision_model_returns_caps_with_vision(self) -> None:
        client = _ollama_client()
        payload = {
            "models": [
                {"name": "gemma4:31b-cloud", "capabilities": ["completion", "tools", "vision", "thinking"]},
                {"name": "nomic-embed-text:latest", "capabilities": ["embedding"]},
            ]
        }

        async def fake_get(url: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(payload)

        _install_fake_get(client, fake_get)
        caps = await client.model_capabilities("gemma4:31b-cloud")
        assert "vision" in caps

    async def test_non_vision_model_returns_caps_without_vision(self) -> None:
        client = _ollama_client()
        payload = {
            "models": [
                {"name": "gemma4:31b-cloud", "capabilities": ["completion", "tools", "vision", "thinking"]},
                {"name": "nomic-embed-text:latest", "capabilities": ["embedding"]},
            ]
        }

        async def fake_get(url: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(payload)

        _install_fake_get(client, fake_get)
        caps = await client.model_capabilities("nomic-embed-text:latest")
        assert caps == ["embedding"]
        assert "vision" not in caps

    async def test_non_ollama_provider_returns_empty_without_http_call(self) -> None:
        client = LLMClient(
            provider="openrouter",
            model="gpt-4o",
            api_key="test-key",
            base_url="https://api.openrouter.ai/v1",
        )
        calls = {"count": 0}

        async def fake_get(url: str, **kwargs: Any) -> FakeResponse:
            calls["count"] += 1
            raise AssertionError("should not be called")

        _install_fake_get(client, fake_get)
        caps = await client.model_capabilities("gpt-4o")
        assert caps == []
        assert calls["count"] == 0

    async def test_unmatched_model_returns_empty(self) -> None:
        client = _ollama_client()
        payload = {"models": [{"name": "nomic-embed-text:latest", "capabilities": ["embedding"]}]}

        async def fake_get(url: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(payload)

        _install_fake_get(client, fake_get)
        caps = await client.model_capabilities("does-not-exist:latest")
        assert caps == []

    async def test_http_error_returns_empty(self) -> None:
        client = _ollama_client()

        async def fake_get(url: str, **kwargs: Any) -> FakeResponse:
            return FakeResponse(error=RuntimeError("boom"))

        _install_fake_get(client, fake_get)
        caps = await client.model_capabilities("gemma4:31b-cloud")
        assert caps == []

    async def test_caching_avoids_redundant_http_call(self) -> None:
        client = _ollama_client()
        calls = {"count": 0}
        payload = {"models": [{"name": "gemma4:31b-cloud", "capabilities": ["vision"]}]}

        async def fake_get(url: str, **kwargs: Any) -> FakeResponse:
            calls["count"] += 1
            return FakeResponse(payload)

        _install_fake_get(client, fake_get)
        await client.model_capabilities("gemma4:31b-cloud")
        await client.model_capabilities("gemma4:31b-cloud")
        assert calls["count"] == 1


class FakeClaude:
    def __init__(self, model: str, caps: list[str]) -> None:
        self.model = model
        self._caps = caps

    async def model_capabilities(self, model: str) -> list[str]:
        return list(self._caps)


class TestCanProcessImages:
    def _make_chat(self, model: str, caps: list[str]) -> CliChat:
        chat = object.__new__(CliChat)
        chat.claude = FakeClaude(model, caps)
        return chat

    async def test_caps_contain_vision_returns_true(self) -> None:
        chat = self._make_chat("some-model", ["vision"])
        assert await chat._can_process_images() is True

    async def test_caps_without_vision_returns_false(self) -> None:
        chat = self._make_chat("some-model", ["completion", "tools"])
        assert await chat._can_process_images() is False

    async def test_unknown_caps_falls_back_to_heuristic_vision(self) -> None:
        chat = self._make_chat("gpt-4o", [])
        assert await chat._can_process_images() is True

    async def test_unknown_caps_falls_back_to_heuristic_non_vision(self) -> None:
        chat = self._make_chat("gemma2", [])
        assert await chat._can_process_images() is False
