from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from mcp_cli.services.logging import get_logger

logger = get_logger(__name__)

WARN_THRESHOLD = 3500
HARD_THRESHOLD = 3800

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_CRITICAL = "critical"


def classify(total: int, warn: int, hard: int) -> str:
    """Classify a token total against warn and hard thresholds.

    ``warn`` is inclusive (total >= warn is a warning), ``hard`` is
    inclusive too (total >= hard is critical).
    """
    if total >= hard:
        return LEVEL_CRITICAL
    if total >= warn:
        return LEVEL_WARN
    return LEVEL_OK


@dataclass
class TokenSample:
    """A single recorded token usage snapshot for one turn."""

    input_tokens: int
    output_tokens: int
    context_tokens: int
    total_tokens: int
    session_id: str
    level: str
    timestamp: float = field(default_factory=time.time)

    @staticmethod
    def level_for(total: int, warn: int, hard: int) -> str:
        """Return the level string for a token total against thresholds."""
        return classify(total, warn, hard)

    @classmethod
    def from_record(
        cls,
        input_tokens: int,
        output_tokens: int,
        context_tokens: int,
        session_id: str,
    ) -> TokenSample:
        """Build a sample, computing total_tokens and level from module defaults."""
        total_tokens = input_tokens + output_tokens + context_tokens
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            context_tokens=context_tokens,
            total_tokens=total_tokens,
            session_id=session_id,
            level=cls.level_for(total_tokens, WARN_THRESHOLD, HARD_THRESHOLD),
        )


class TokenMonitor:
    """In-memory, synchronous token usage monitor.

    Records per-turn token counts, aggregates recent history, and produces
    fallback signals for a UI layer. Pure logic: no network, no LLM calls.
    """

    def __init__(
        self,
        warn_threshold: int = WARN_THRESHOLD,
        hard_threshold: int = HARD_THRESHOLD,
        model: str | None = None,
        max_recent: int = 200,
    ) -> None:
        self.warn_threshold = warn_threshold
        self.hard_threshold = hard_threshold
        self.model = model
        self.max_recent = max_recent
        self._samples: deque[TokenSample] = deque(maxlen=max_recent)

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        context_tokens: int = 0,
        session_id: str = "default",
    ) -> dict:
        """Record a turn's token usage and return its status dict."""
        total_tokens = input_tokens + output_tokens + context_tokens
        level = classify(total_tokens, self.warn_threshold, self.hard_threshold)
        sample = TokenSample(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            context_tokens=context_tokens,
            total_tokens=total_tokens,
            session_id=session_id,
            level=level,
        )
        self._samples.append(sample)
        logger.debug(
            "token monitor: session=%s in=%d out=%d ctx=%d total=%d level=%s",
            session_id,
            input_tokens,
            output_tokens,
            context_tokens,
            total_tokens,
            level,
        )
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "context_tokens": context_tokens,
            "level": level,
            "warn_threshold": self.warn_threshold,
            "hard_threshold": self.hard_threshold,
        }

    def _filtered(self, session_id: str | None) -> list[TokenSample]:
        if session_id is None:
            return list(self._samples)
        return [s for s in self._samples if s.session_id == session_id]

    def status(self, session_id: str | None = None) -> dict:
        """Aggregate the recent window, optionally scoped to one session."""
        samples = self._filtered(session_id)
        if not samples:
            return {
                "recent_count": 0,
                "last": None,
                "avg_input": 0,
                "avg_output": 0,
                "max_total": 0,
                "level": LEVEL_OK,
                "warnings": 0,
                "critical_hits": 0,
            }
        last = samples[-1]
        return {
            "recent_count": len(samples),
            "last": {
                "input_tokens": last.input_tokens,
                "output_tokens": last.output_tokens,
                "total_tokens": last.total_tokens,
                "context_tokens": last.context_tokens,
                "level": last.level,
                "session_id": last.session_id,
            },
            "avg_input": sum(s.input_tokens for s in samples) // len(samples),
            "avg_output": sum(s.output_tokens for s in samples) // len(samples),
            "max_total": max(s.total_tokens for s in samples),
            "level": last.level,
            "warnings": sum(1 for s in samples if s.level == LEVEL_WARN),
            "critical_hits": sum(1 for s in samples if s.level == LEVEL_CRITICAL),
        }

    def should_fallback(self) -> bool:
        """True when the latest sample is warn/critical or recent average is over warn."""
        if not self._samples:
            return False
        latest = self._samples[-1]
        if latest.level in (LEVEL_WARN, LEVEL_CRITICAL):
            return True
        avg_total = sum(s.total_tokens for s in self._samples) // len(self._samples)
        return avg_total >= self.warn_threshold

    def fallback_action(self) -> str:
        """Signal for UI fallback: ``compress``, ``truncate``, or ``none``."""
        if not self._samples:
            return "none"
        latest = self._samples[-1]
        if latest.level == LEVEL_CRITICAL:
            return "truncate"
        if latest.level == LEVEL_WARN:
            return "compress"
        return "none"

    def reset(self, session_id: str | None = None) -> None:
        """Clear all samples, or only those belonging to a session."""
        if session_id is None:
            self._samples.clear()
            return
        self._samples = deque(
            (s for s in self._samples if s.session_id != session_id),
            maxlen=self.max_recent,
        )

    def sample_count(self) -> int:
        """Total number of samples currently held."""
        return len(self._samples)


def format_status(status: dict) -> str:
    """Render a status dict as a single human-readable line."""
    if "total_tokens" not in status and status.get("last"):
        status = status["last"]
    total = status.get("total_tokens", 0)
    input_tokens = status.get("input_tokens", 0)
    output_tokens = status.get("output_tokens", 0)
    level = status.get("level", LEVEL_OK)
    return f"tokens: {total} (in {input_tokens} / out {output_tokens}) [{level}]"
