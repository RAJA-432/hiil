from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcp_cli.services.verifier import Verdict, Verifier


class FakeClaude:
    def __init__(
        self,
        model: str = "test-model",
        response: Any | None = None,
        error: Exception | None = None,
    ) -> None:
        self.model = model
        self._response = response
        self._error = error
        self.calls: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        if self._error is not None:
            raise self._error
        return self._response


def _verdict_payload() -> str:
    return '{"valid": true, "score": 1.0, "issues": [], "revised": null}'


class TestVerifyParsing:
    async def test_valid_json_returns_valid_verdict(self) -> None:
        fake = FakeClaude(response=SimpleNamespace(content=_verdict_payload()))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.valid is True
        assert verdict.score == 1.0
        assert verdict.issues == []
        assert verdict.revised is None

    async def test_invalid_answer_parses_issues_and_revised(self) -> None:
        content = (
            '{"valid": false, "score": 0.4, '
            '"issues": ["hallucination"], "revised": "corrected answer"}'
        )
        fake = FakeClaude(response=SimpleNamespace(content=content))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.valid is False
        assert verdict.score == 0.4
        assert verdict.issues == ["hallucination"]
        assert verdict.revised == "corrected answer"

    async def test_json_wrapped_in_fences_is_parsed(self) -> None:
        content = f"```json\n{_verdict_payload()}\n```"
        fake = FakeClaude(response=SimpleNamespace(content=content))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.valid is True
        assert verdict.score == 1.0

    async def test_list_content_parts_are_joined(self) -> None:
        content = [
            {"type": "text", "text": '{"valid": true, "score": 1.0'},
            {"type": "text", "text": ', "issues": [], "revised": null}'},
        ]
        fake = FakeClaude(response=SimpleNamespace(content=content))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.valid is True
        assert verdict.score == 1.0
        assert verdict.issues == []

    async def test_list_content_objects_with_text_attribute_are_joined(self) -> None:
        content = [
            SimpleNamespace(text='{"valid": true, "score": 1.0'),
            SimpleNamespace(text=', "issues": [], "revised": null}'),
        ]
        fake = FakeClaude(response=SimpleNamespace(content=content))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.valid is True
        assert verdict.score == 1.0


class TestVerifyFailSoft:
    async def test_exception_returns_failsoft_verdict(self) -> None:
        fake = FakeClaude(error=RuntimeError("boom"))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict == Verdict(valid=True, score=1.0, issues=[], revised=None)

    async def test_garbage_content_returns_failsoft_verdict(self) -> None:
        fake = FakeClaude(response=SimpleNamespace(content="this is not json"))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict == Verdict(valid=True, score=1.0, issues=[], revised=None)

    async def test_missing_keys_return_failsoft_verdict(self) -> None:
        fake = FakeClaude(response=SimpleNamespace(content='{"issues": []}'))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict == Verdict(valid=True, score=1.0, issues=[], revised=None)

    async def test_null_content_returns_failsoft_verdict(self) -> None:
        fake = FakeClaude(response=SimpleNamespace(content=None))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict == Verdict(valid=True, score=1.0, issues=[], revised=None)


class TestVerifyScoreClamping:
    async def test_score_clamped_to_upper_bound(self) -> None:
        content = '{"valid": true, "score": 1.5, "issues": [], "revised": null}'
        fake = FakeClaude(response=SimpleNamespace(content=content))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.score == 1.0

    async def test_score_clamped_to_lower_bound(self) -> None:
        content = '{"valid": true, "score": -0.2, "issues": [], "revised": null}'
        fake = FakeClaude(response=SimpleNamespace(content=content))
        verdict = await Verifier(fake).verify("answer", "question")
        assert verdict.score == 0.0


class TestVerifyCallArgs:
    async def test_response_format_json_object_is_passed(self) -> None:
        fake = FakeClaude(response=SimpleNamespace(content=_verdict_payload()))
        verifier = Verifier(fake)
        await verifier.verify("answer", "question")
        assert len(fake.calls) == 1
        _, kwargs = fake.calls[0]
        assert kwargs["response_format"] == {"type": "json_object"}

    async def test_messages_include_answer_question_and_context(self) -> None:
        fake = FakeClaude(response=SimpleNamespace(content=_verdict_payload()))
        verifier = Verifier(fake)
        await verifier.verify(
            "the answer",
            "the question",
            rag_context="some context",
            tool_summary="tool output",
        )
        messages, _ = fake.calls[0]
        assert messages[0]["role"] == "system"
        user_content = messages[1]["content"]
        assert "the answer" in user_content
        assert "the question" in user_content
        assert "some context" in user_content
        assert "tool output" in user_content


class TestVerifierModel:
    async def test_model_defaults_to_claude_model(self) -> None:
        fake = FakeClaude(model="default-model")
        assert Verifier(fake).model == "default-model"

    async def test_custom_model_is_used(self) -> None:
        fake = FakeClaude(model="default-model")
        assert Verifier(fake, model="custom-model").model == "custom-model"
