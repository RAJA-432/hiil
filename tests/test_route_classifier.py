from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from mcp_cli.config import load_settings
from mcp_cli.services.agents.route_classifier import (
    RouteClassifier,
    classify,
    classify_rule_based,
    classify_with_model,
)
from mcp_cli.services.chat import CliChat


class _FakeLLM:
    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict]):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.content)


class TestRuleBased:
    def test_email_request_routes_to_inbox_manager(self):
        assert classify_rule_based("show me my emails") == "inbox-manager"

    def test_inbox_request_routes_to_inbox_manager(self):
        assert classify_rule_based("read my inbox please") == "inbox-manager"

    def test_quote_request_routes_to_quote_reviewer(self):
        assert classify_rule_based("get a quote for the order") == "quote-reviewer"

    def test_pricing_request_routes_to_quote_reviewer(self):
        assert classify_rule_based("update the pricing on this proposal") == "quote-reviewer"

    @pytest.mark.parametrize(
        "request_text",
        [
            "query the chinook database",
            "run a sqlite query",
            "check the database for customers",
        ],
    )
    def test_database_requests_route_to_chinook_analyst(self, request_text):
        assert classify_rule_based(request_text) == "chinook-analyst"

    def test_unknown_request_returns_none(self):
        assert classify_rule_based("what is the weather in london?") is None

    def test_empty_request_returns_none(self):
        assert classify_rule_based("") is None

    def test_genre_request_routes_to_genre_researcher(self):
        assert classify_rule_based("list tracks for the jazz genre") == "genre-researcher"


class TestModelPath:
    async def test_model_returning_registry_name(self):
        llm = _FakeLLM(content="inbox-manager")
        assert await classify_with_model("read my emails", llm) == "inbox-manager"

    async def test_model_returning_none(self):
        llm = _FakeLLM(content="none")
        assert await classify_with_model("hello there", llm) is None

    async def test_model_raising_returns_none(self):
        llm = _FakeLLM(error=RuntimeError("boom"))
        assert await classify_with_model("read my emails", llm) is None

    async def test_model_absent_returns_none(self):
        assert await classify_with_model("read my emails", None) is None

    async def test_classify_uses_model_when_llm_provided(self):
        llm = _FakeLLM(content="quote-reviewer")
        assert await classify("give me a quote", llm) == "quote-reviewer"

    async def test_classify_falls_back_to_rule_based_without_llm(self):
        assert await classify("read my inbox") == "inbox-manager"

    async def test_classifier_instance_model_path(self):
        llm = _FakeLLM(content="chinook-analyst")
        classifier = RouteClassifier()
        assert await classifier.classify("analyze the database", llm) == "chinook-analyst"
        assert await classifier.classify("analyze the database") == "chinook-analyst"


class TestSettingsToggle:
    def test_load_settings_defaults_intent_routing_off(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("settings:\n  provider: ollama\n  model: m\n  api_key: ''\n")
        settings, _ = load_settings(str(cfg))
        assert settings.intent_routing is False

    def test_load_settings_parses_intent_routing(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("settings:\n  provider: ollama\n  model: m\n  api_key: ''\n  intent_routing: true\n")
        settings, _ = load_settings(str(cfg))
        assert settings.intent_routing is True

    def test_load_settings_reads_intent_routing_from_env(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("settings:\n  provider: ollama\n  model: m\n  api_key: ''\n")
        monkeypatch.setenv("INTENT_ROUTING", "1")
        settings, _ = load_settings(str(cfg))
        assert settings.intent_routing is True


class _FakeClaude:
    model = "test-model"


class _FakeStreamer:
    def __init__(self, message: SimpleNamespace | None = None) -> None:
        self.message = message or SimpleNamespace(content="direct reply", tool_calls=None)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        self.calls.append(messages)
        return self.message, 5, 5


class _FakeDocInjector:
    async def resolve(self, text: str) -> str:
        return text


class _FakeRag:
    async def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.25) -> list[dict]:
        return []

    def format_context(self, results: list[dict]) -> str:
        return ""


class _FakeContext:
    def trim(self, messages: list[dict], tools_tokens: int = 0) -> list[dict]:
        return messages

    async def auto_index(self, text: str, namespace: str = "messages") -> None:
        return None


class _FakeHistory:
    def load_session(self, session_id: str) -> list[dict]:
        return []

    async def async_save_message(self, session_id: str, role: str, content: str) -> None:
        pass


class _FakeUsage:
    async def async_record(self, model: str, input_tokens: int, output_tokens: int, session_id: str = "default") -> None:
        pass


def _make_chat(intent_routing: bool = False) -> CliChat:
    chat = object.__new__(CliChat)
    chat.intent_routing = intent_routing
    chat.claude = _FakeClaude()
    chat.messages = []
    chat.session_id = "test-session"
    chat.history = _FakeHistory()
    chat.usage = _FakeUsage()
    chat.context = _FakeContext()
    chat.rag = _FakeRag()
    chat.doc_injector = _FakeDocInjector()
    chat.streamer = _FakeStreamer()
    chat.tool_runner = None
    chat.verifier = None
    chat.moderation = None
    chat.response_format = None
    chat._correction_attempts = 0
    chat.MAX_CORRECTION_ATTEMPTS = 2
    chat._max_tool_iterations = 10
    chat._openai_tools = []
    chat._auto_index_task = None
    return chat


class TestDispatchWiring:
    async def test_intent_routing_off_does_not_invoke_classifier(self):
        chat = _make_chat(intent_routing=False)
        with patch("mcp_cli.services.chat.classify") as classify_mock:
            result = await chat.send("read my inbox")
        classify_mock.assert_not_called()
        assert result == "direct reply"
        assert chat.streamer.calls, "normal LLM path should still run"

    async def test_intent_routing_on_dispatches_to_agent(self):
        chat = _make_chat(intent_routing=True)

        async def fake_run(task_input: str) -> SimpleNamespace:
            return SimpleNamespace(status="completed", output="agent output", tool_calls_made=0)

        runner = SimpleNamespace(run=fake_run)
        with (
            patch("mcp_cli.services.chat.classify", AsyncMock(return_value="inbox-manager")) as classify_mock,
            patch.object(chat, "spawn_agent", return_value=runner) as spawn_mock,
        ):
            result = await chat.send("read my inbox")

        classify_mock.assert_awaited_once()
        assert classify_mock.await_args.args[0] == "read my inbox"
        spawn_mock.assert_called_once()
        assert result == "agent output"
        assert chat.streamer.calls == [], "agent dispatch should skip the normal LLM path"

    async def test_intent_routing_on_unknown_agent_falls_through(self):
        chat = _make_chat(intent_routing=True)
        with patch("mcp_cli.services.chat.classify", AsyncMock(return_value=None)):
            result = await chat.send("read my inbox")
        assert result == "direct reply"
        assert chat.streamer.calls, "falls through to the normal LLM path"
