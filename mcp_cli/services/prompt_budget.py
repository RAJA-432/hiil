"""Token-aware prompt formatting and budgeting helpers for the RAG pipeline.

Pure library module: no I/O and no network calls, so it can be unit tested
without any live model access or running services.
"""

from __future__ import annotations

from collections.abc import Callable

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)

_SEPARATOR = "\n\n---\n\n"
_DEFAULT_MODEL = "gpt-4o"


def estimate_tokens(text: str, model: str | None = None) -> int:
    """Estimate the number of tokens in *text*.

    Prefers ``mcp_cli.services.usage.count_tokens`` when it is importable and
    callable (a pure local computation over tiktoken); otherwise falls back to
    a word-count heuristic so this module stays hermetic.
    """
    try:
        from mcp_cli.services.usage import count_tokens

        return max(0, int(count_tokens(text, model or _DEFAULT_MODEL)))
    except Exception:
        return max(0, len(text.split()))


def default_format_chunk(chunk: dict, index: int = 0) -> str:
    """Format a single retrieved chunk in the same spirit as ``rag.format_context``."""
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    source = metadata.get("filename", "unknown")
    score = chunk.get("score", 0.0)
    return f"[{index + 1}] (source: {source}, score: {score:.3f})\n{chunk.get('text', '')}"


class PromptBudget:
    """Keep an assembled RAG prompt (system + context + question) within a token budget."""

    def __init__(
        self,
        max_tokens: int = 4096,
        reserve_output: int = 1024,
        model: str | None = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.reserve_output = reserve_output
        self.model = model

    @property
    def context_budget(self) -> int:
        """Tokens available for prompt assembly after reserving model output."""
        return max(0, self.max_tokens - self.reserve_output)

    def _base_tokens(self, system_prompt: str, question: str) -> int:
        return estimate_tokens(system_prompt, self.model) + estimate_tokens(question, self.model)

    def fit_context(
        self,
        chunks: list[dict],
        system_prompt: str,
        question: str,
        format_chunk: Callable[[dict], str] | None = None,
    ) -> dict:
        """Greedily assemble as many leading chunks as fit the context budget.

        Chunks are assumed to be ranked best-first. The running estimate covers
        the full prompt (system + context + question) and never exceeds
        ``context_budget()``, even if that means including zero context.
        """
        budget = self.context_budget
        base = self._base_tokens(system_prompt, question)
        selected: list[dict] = []
        parts: list[str] = []
        total_est = base
        for i, chunk in enumerate(chunks):
            part = default_format_chunk(chunk, i) if format_chunk is None else format_chunk(chunk)
            candidate_parts = parts + [part]
            candidate_est = base + estimate_tokens(_SEPARATOR.join(candidate_parts), self.model)
            if candidate_est > budget:
                break
            parts = candidate_parts
            selected.append(chunk)
            total_est = candidate_est
        return {
            "context": _SEPARATOR.join(parts),
            "selected": selected,
            "dropped": len(chunks) - len(selected),
            "estimated_prompt_tokens": total_est,
            "within_budget": total_est <= budget,
            "remaining": budget - total_est,
        }

    def needs_fallback(self, assembled: dict) -> bool:
        """True when the assembled prompt overflows the context budget."""
        if not assembled.get("within_budget", True):
            return True
        return int(assembled.get("estimated_prompt_tokens", 0)) > self.context_budget

    def suggest_top_k(self, chunks: list[dict], question: str, system_prompt: str = "") -> int:
        """Return the max number of leading chunks that fit within the budget."""
        budget = self.context_budget
        base = self._base_tokens(system_prompt, question)
        parts: list[str] = []
        k = 0
        for i, chunk in enumerate(chunks):
            part = default_format_chunk(chunk, i)
            candidate_est = base + estimate_tokens(_SEPARATOR.join(parts + [part]), self.model)
            if candidate_est > budget:
                break
            parts.append(part)
            k += 1
        return k


class TokenAwareSampler:
    """Plan output limits and pick the smallest adequate model for a request."""

    def __init__(
        self,
        max_total: int = 4096,
        reserve_output: int = 1024,
        model: str | None = None,
    ) -> None:
        self.max_total = max_total
        self.reserve_output = reserve_output
        self.model = model

    def plan(self, input_tokens: int, requested_output: int) -> dict:
        """Clamp the requested output so input + output stays within ``max_total``."""
        max_output_tokens = max(1, self.max_total - input_tokens)
        within_budget = input_tokens + requested_output <= self.max_total
        overflow = max(0, requested_output - max_output_tokens)
        return {
            "max_output_tokens": max_output_tokens,
            "within_budget": within_budget,
            "overflow": overflow,
        }

    def select_model(self, input_tokens: int, candidates: list[dict]) -> dict | None:
        """Pick the smallest adequate candidate that fits *input_tokens* with output room."""
        for candidate in sorted(candidates, key=lambda c: c.get("context_window", 0)):
            window = int(candidate.get("context_window", 0))
            max_output = int(candidate.get("max_output", 0))
            if input_tokens <= window and (window - input_tokens) >= 1 and max_output >= 1:
                return candidate
        return None
