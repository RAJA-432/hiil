from __future__ import annotations

import sys
from unittest.mock import patch

from mcp_cli.services.prompt_budget import (
    PromptBudget,
    TokenAwareSampler,
    default_format_chunk,
    estimate_tokens,
)


def _chunk(text: str, score: float = 0.9, filename: str = "doc.txt") -> dict:
    return {"key": "k", "text": text, "score": score, "metadata": {"filename": filename}}


class TestEstimateTokens:
    def test_empty_string_is_zero(self) -> None:
        assert estimate_tokens("") == 0

    def test_non_negative_for_any_text(self) -> None:
        assert estimate_tokens("hello world") >= 1
        assert estimate_tokens("a" * 500) >= estimate_tokens("a" * 10)

    def test_falls_back_when_usage_count_raises(self) -> None:
        with patch("mcp_cli.services.usage.count_tokens", side_effect=RuntimeError("boom")):
            assert estimate_tokens("one two three") == 3

    def test_falls_back_when_usage_import_unavailable(self) -> None:
        with patch.dict(sys.modules, {"mcp_cli.services.usage": None}):
            assert estimate_tokens("one two three") == 3


class TestDefaultFormatChunk:
    def test_matches_rag_style(self) -> None:
        chunk = _chunk("hello world", score=0.9, filename="doc.txt")
        assert default_format_chunk(chunk) == "[1] (source: doc.txt, score: 0.900)\nhello world"

    def test_handles_missing_metadata(self) -> None:
        assert default_format_chunk({"text": "hi"}) == "[1] (source: unknown, score: 0.000)\nhi"


class TestFitContext:
    def _budget(self, context_budget: int) -> PromptBudget:
        return PromptBudget(max_tokens=context_budget + 20, reserve_output=20)

    def test_never_exceeds_budget(self) -> None:
        budget = self._budget(80)
        chunks = [_chunk("word " * 15) for _ in range(5)]
        result = budget.fit_context(chunks, "s", "q")
        assert result["estimated_prompt_tokens"] <= budget.context_budget
        assert len(result["selected"]) == 2
        assert result["dropped"] == 3
        assert result["within_budget"] is True
        assert result["remaining"] >= 0

    def test_includes_all_when_they_fit(self) -> None:
        budget = PromptBudget()
        chunks = [_chunk("word " * 3) for _ in range(3)]
        result = budget.fit_context(chunks, "s", "q")
        assert result["dropped"] == 0
        assert len(result["selected"]) == 3
        assert result["context"].count("\n\n---\n\n") == 2
        assert result["within_budget"] is True

    def test_overflow_keeps_zero_context(self) -> None:
        budget = self._budget(40)
        chunks = [_chunk("word " * 15) for _ in range(5)]
        result = budget.fit_context(chunks, "word " * 300, "q")
        assert result["selected"] == []
        assert result["dropped"] == 5
        assert result["context"] == ""
        assert result["within_budget"] is False

    def test_respects_format_chunk_override(self) -> None:
        budget = PromptBudget()
        chunks = [_chunk("alpha"), _chunk("beta")]
        result = budget.fit_context(chunks, "", "q", format_chunk=lambda c: f"<{c['text']}>")
        assert result["context"] == "<alpha>\n\n---\n\n<beta>"
        assert [c["text"] for c in result["selected"]] == ["alpha", "beta"]


class TestNeedsFallback:
    def test_true_on_overflow(self) -> None:
        budget = PromptBudget(max_tokens=100, reserve_output=20)
        assembled = {"estimated_prompt_tokens": 5000, "within_budget": False}
        assert budget.needs_fallback(assembled) is True

    def test_true_when_tokens_exceed_budget(self) -> None:
        budget = PromptBudget(max_tokens=100, reserve_output=20)
        assembled = {"estimated_prompt_tokens": 200, "within_budget": True}
        assert budget.needs_fallback(assembled) is True

    def test_false_when_within_budget(self) -> None:
        budget = PromptBudget()
        assert budget.needs_fallback({"estimated_prompt_tokens": 100, "within_budget": True}) is False


class TestSuggestTopK:
    def test_returns_fit_count(self) -> None:
        budget = PromptBudget(max_tokens=100, reserve_output=20)
        chunks = [_chunk("word " * 15) for _ in range(5)]
        assert budget.suggest_top_k(chunks, "q", "s") == 2

    def test_mixed_big_and_small(self) -> None:
        budget = PromptBudget(max_tokens=60, reserve_output=20)
        chunks = [_chunk("word " * 3), _chunk("word " * 39), _chunk("word " * 3)]
        assert budget.suggest_top_k(chunks, "q") == 1

    def test_empty_chunks(self) -> None:
        budget = PromptBudget()
        assert budget.suggest_top_k([], "q") == 0


class TestTokenAwareSampler:
    def test_plan_clamps_output_to_budget(self) -> None:
        sampler = TokenAwareSampler(max_total=100, reserve_output=10)
        plan = sampler.plan(input_tokens=80, requested_output=50)
        assert plan == {"max_output_tokens": 20, "within_budget": False, "overflow": 30}

    def test_plan_within_budget(self) -> None:
        sampler = TokenAwareSampler(max_total=100)
        plan = sampler.plan(input_tokens=40, requested_output=30)
        assert plan == {"max_output_tokens": 60, "within_budget": True, "overflow": 0}

    def test_plan_input_over_total_still_outputs_one(self) -> None:
        sampler = TokenAwareSampler(max_total=100)
        plan = sampler.plan(input_tokens=120, requested_output=10)
        assert plan["max_output_tokens"] == 1
        assert plan["within_budget"] is False
        assert plan["overflow"] == 9

    def test_select_model_picks_smallest_adequate(self) -> None:
        sampler = TokenAwareSampler()
        candidates = [
            {"id": "tiny", "context_window": 1024, "max_output": 256},
            {"id": "small", "context_window": 4096, "max_output": 1024},
            {"id": "big", "context_window": 32768, "max_output": 8192},
        ]
        assert sampler.select_model(200, candidates)["id"] == "tiny"
        assert sampler.select_model(1024, candidates)["id"] == "small"
        assert sampler.select_model(2000, candidates)["id"] == "small"
        assert sampler.select_model(5000, candidates)["id"] == "big"
        assert sampler.select_model(40000, candidates) is None

    def test_select_model_skips_candidate_without_output_room(self) -> None:
        sampler = TokenAwareSampler()
        candidates = [
            {"id": "noout", "context_window": 512, "max_output": 0},
            {"id": "tiny", "context_window": 1024, "max_output": 256},
        ]
        assert sampler.select_model(200, candidates)["id"] == "tiny"
