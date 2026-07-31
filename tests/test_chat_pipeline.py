from __future__ import annotations

import contextlib
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from mcp_cli.services.chat import CliChat
from mcp_cli.services.moderation import ModerationFilter
from mcp_cli.services.verifier import Verdict, Verifier


class FakeClaude:
    model = "test-model"


class FakeStreamer:
    def __init__(self, messages: list[Any]) -> None:
        self._messages = list(messages)
        self.calls: list[list[dict[str, Any]]] = []

    async def chat(self, messages, tools=None, on_chunk=None, response_format=None):
        self.calls.append(messages)
        message = self._messages.pop(0)
        content = getattr(message, "content", "") or ""
        input_tokens = len(json.dumps([m.get("content", "") for m in messages]))
        output_tokens = len(content)
        return message, input_tokens, output_tokens


class FakeContext:
    def trim(self, messages: list[dict[str, Any]], tools_tokens: int = 0) -> list[dict[str, Any]]:
        return messages

    async def auto_index(self, text: str, namespace: str = "messages") -> None:
        return None


class FakeHistory:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str]] = []

    def load_session(self, session_id: str) -> list[dict[str, Any]]:
        return []

    async def async_save_message(self, session_id: str, role: str, content: str) -> None:
        self.saved.append((session_id, role, content))


class FakeDocInjector:
    async def resolve(self, text: str) -> str:
        return text


class FakeUsage:
    def __init__(self) -> None:
        self.records: list[tuple[str, int, int, str]] = []

    async def async_record(self, model: str, input_tokens: int, output_tokens: int, session_id: str = "default") -> None:
        self.records.append((model, input_tokens, output_tokens, session_id))


class FakeRag:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = results or []
        self.retrieved = 0

    async def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.25) -> list[dict[str, Any]]:
        self.retrieved += 1
        return list(self._results)

    def format_context(self, results: list[dict[str, Any]]) -> str:
        return "\n\n".join(r["text"] for r in results)


class FakeToolRunner:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def execute_tool_calls(self, tool_calls: list[Any], on_tool_event: Any = None, on_approval: Any = None) -> list[dict[str, Any]]:
        self.calls.append(tool_calls)
        return [{"role": "tool", "tool_call_id": "call_1", "content": "result"}]


class FakeVerifier:
    def __init__(self, verdict: Verdict | None = None, error: Exception | None = None) -> None:
        self.verdict = verdict or Verdict(valid=True, score=1.0, issues=[], revised=None)
        self.error = error
        self.calls: list[tuple[str, str, str, str]] = []

    async def verify(self, answer: str, user_input: str, rag_context: str = "", tool_summary: str = "") -> Verdict:
        self.calls.append((answer, user_input, rag_context, tool_summary))
        if self.error is not None:
            raise self.error
        return self.verdict


class FakeModeration:
    def __init__(self, input_ok: bool = True, output_ok: bool = True, input_reason: str = "", output_reason: str = "") -> None:
        self._input_ok = input_ok
        self._output_ok = output_ok
        self._input_reason = input_reason
        self._output_reason = output_reason
        self.input_checks: list[str] = []
        self.output_checks: list[str] = []

    def check_input(self, text: str) -> tuple[bool, str]:
        self.input_checks.append(text)
        return self._input_ok, self._input_reason

    def check_output(self, text: str) -> tuple[bool, str]:
        self.output_checks.append(text)
        return self._output_ok, self._output_reason


def _tool_message(name: str = "get_weather") -> SimpleNamespace:
    return SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(function=SimpleNamespace(name=name, arguments='{"q": "London"}'))],
    )


def _answer_message(content: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=None)


def _make_chat(
    *,
    messages: list[Any] | None = None,
    verifier: FakeVerifier | None = None,
    moderation: FakeModeration | None = None,
    rag_results: list[dict[str, Any]] | None = None,
    tool_runner: FakeToolRunner | None = None,
) -> CliChat:
    chat = object.__new__(CliChat)
    chat.claude = SimpleNamespace(model="test-model")
    chat.messages = []
    chat.session_id = "test-session"
    chat.history = FakeHistory()
    chat.usage = FakeUsage()
    chat.context = FakeContext()
    chat.rag = FakeRag(rag_results)
    chat.doc_injector = FakeDocInjector()
    chat.streamer = FakeStreamer(messages or [_answer_message()])
    chat.tool_runner = tool_runner or FakeToolRunner()
    chat.verifier = verifier
    chat.moderation = moderation
    chat.response_format = None
    chat._correction_attempts = 0
    chat.MAX_CORRECTION_ATTEMPTS = 2
    chat._max_tool_iterations = 10
    chat._openai_tools = []
    chat._auto_index_task = None
    return chat


async def _send(chat: CliChat, text: str = "hello") -> str:
    result = await chat.send(text)
    task = chat._auto_index_task
    if task is not None:
        with contextlib.suppress(Exception):
            await task
    return result


def _construct_chat(**kwargs: Any) -> CliChat:
    with (
        patch("mcp_cli.services.chat.ChatHistoryManager", FakeHistory),
        patch("mcp_cli.services.chat.UsageTracker", FakeUsage),
        patch("mcp_cli.services.chat.VectorStore"),
        patch("mcp_cli.services.chat.Streamer"),
        patch("mcp_cli.services.chat.ContextManager"),
        patch("mcp_cli.services.chat.RagPipeline"),
        patch("mcp_cli.services.chat.ToolRunner"),
        patch("mcp_cli.services.chat.DocumentInjector"),
    ):
        return CliChat(
            doc_client=None,
            clients={},
            claude_service=SimpleNamespace(model="m"),
            **kwargs,
        )


class TestConstructorWiring:
    def test_disabled_by_default(self) -> None:
        chat = _construct_chat()
        assert chat.verifier is None
        assert chat.moderation is None

    def test_enabled_builds_verifier_and_moderation(self) -> None:
        chat = _construct_chat(
            enable_verification=True,
            verifier_model="critic-model",
            enable_moderation=True,
            moderation_deny_list=["spam"],
        )
        assert isinstance(chat.verifier, Verifier)
        assert chat.verifier.model == "critic-model"
        assert isinstance(chat.moderation, ModerationFilter)
        assert chat.moderation.check_input("spam here") == (False, "deny_list")

    def test_verifier_skipped_when_no_claude(self) -> None:
        with (
            patch("mcp_cli.services.chat.ChatHistoryManager", FakeHistory),
            patch("mcp_cli.services.chat.UsageTracker", FakeUsage),
            patch("mcp_cli.services.chat.VectorStore"),
            patch("mcp_cli.services.chat.Streamer"),
            patch("mcp_cli.services.chat.ContextManager"),
            patch("mcp_cli.services.chat.RagPipeline"),
            patch("mcp_cli.services.chat.ToolRunner"),
            patch("mcp_cli.services.chat.DocumentInjector"),
        ):
            chat = CliChat(
                doc_client=None,
                clients={},
                claude_service=None,
                enable_verification=True,
            )
        assert chat.verifier is None


class TestInputModeration:
    async def test_blocked_input_returns_refusal_and_saves_nothing(self) -> None:
        moderation = FakeModeration(input_ok=False, input_reason="violence")
        chat = _make_chat(moderation=moderation)
        result = await _send(chat)
        assert result == "[blocked] Your message was flagged by moderation (violence)."
        assert chat.history.saved == []

    async def test_input_moderation_not_set_allows_normal_flow(self) -> None:
        chat = _make_chat()
        result = await _send(chat)
        assert result == "hello"
        assert len(chat.history.saved) == 2
        assert chat.history.saved[0][1] == "user"


class TestVerification:
    async def test_verifier_runs_when_tool_used(self) -> None:
        verifier = FakeVerifier(Verdict(valid=True, score=1.0, issues=[], revised=None))
        chat = _make_chat(
            messages=[_tool_message(), _answer_message("final answer")],
            verifier=verifier,
        )
        result = await _send(chat, "what is the weather?")
        assert result == "final answer"
        assert len(verifier.calls) == 1
        answer, user_input, rag_context, tool_summary = verifier.calls[0]
        assert answer == "final answer"
        assert user_input == "what is the weather?"
        assert rag_context == ""
        assert "get_weather" in tool_summary
        assert len(chat.usage.records) == 3

    async def test_verifier_runs_when_rag_context_present(self) -> None:
        verifier = FakeVerifier(Verdict(valid=True, score=1.0, issues=[], revised=None))
        chat = _make_chat(
            rag_results=[{"text": "knowledge context", "score": 0.9, "metadata": {"filename": "doc.md"}}],
            verifier=verifier,
        )
        result = await _send(chat, "how do I use x?")
        assert result == "hello"
        assert len(verifier.calls) == 1
        _, _, rag_context, _ = verifier.calls[0]
        assert "knowledge context" in rag_context

    async def test_verifier_not_called_without_tools_or_rag(self) -> None:
        verifier = FakeVerifier(Verdict(valid=True, score=1.0, issues=[], revised=None))
        chat = _make_chat(verifier=verifier)
        result = await _send(chat)
        assert result == "hello"
        assert verifier.calls == []

    async def test_verifier_disabled_is_never_called(self) -> None:
        tool_runner = FakeToolRunner()
        chat = _make_chat(
            messages=[_tool_message(), _answer_message("final answer")],
            tool_runner=tool_runner,
            verifier=None,
        )
        result = await _send(chat)
        assert result == "final answer"
        assert len(tool_runner.calls) == 1
        assert len(chat.usage.records) == 2

    async def test_verifier_fail_soft_returns_original_answer(self) -> None:
        verifier = FakeVerifier(error=RuntimeError("boom"))
        chat = _make_chat(
            messages=[_tool_message(), _answer_message("final answer")],
            verifier=verifier,
        )
        result = await _send(chat, "what is the weather?")
        assert result == "final answer"
        assert len(verifier.calls) == 1

    async def test_verifier_revised_answer_is_returned(self) -> None:
        verifier = FakeVerifier(
            Verdict(valid=False, score=0.3, issues=["hallucination"], revised="corrected answer")
        )
        chat = _make_chat(
            messages=[_tool_message(), _answer_message("original answer")],
            verifier=verifier,
        )
        result = await _send(chat, "what is the weather?")
        assert result == "corrected answer"
        assert len(verifier.calls) == 1

    async def test_verifier_issues_trigger_single_correction_retry(self) -> None:
        verifier = FakeVerifier(Verdict(valid=False, score=0.4, issues=["hallucination"], revised=None))
        chat = _make_chat(
            messages=[_tool_message(), _answer_message("original answer"), _answer_message("corrected answer")],
            verifier=verifier,
        )
        result = await _send(chat, "what is the weather?")
        assert result == "corrected answer"
        assert len(verifier.calls) == 1
        assert len(chat.streamer.calls) == 3
        correction_message = chat.streamer.calls[2][-1]
        assert correction_message["role"] == "user"
        assert "hallucination" in correction_message["content"]


class TestOutputModeration:
    async def test_blocked_output_returns_refusal(self) -> None:
        moderation = FakeModeration(output_ok=False, output_reason="explicit")
        chat = _make_chat(moderation=moderation)
        result = await _send(chat)
        assert result == "[blocked] Your message was flagged by moderation (explicit)."

    async def test_clean_output_passes_through(self) -> None:
        moderation = FakeModeration(output_ok=True)
        chat = _make_chat(moderation=moderation)
        result = await _send(chat)
        assert result == "hello"
        assert moderation.output_checks == ["hello"]
