"""LLM-backed and heuristic judging for evaluation scenarios."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger("eval.judge")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_TOOL_MARKERS = (
    "tool_call",
    "tool_use",
    "tool_result",
    "function_call",
    "[tool",
)

_SYSTEM_PROMPT = (
    'You are a strict, impartial evaluator for an AI assistant. '
    'Respond with a single JSON object with keys "score" (float 0-1), '
    '"pass" (boolean), and "rationale" (short string). '
    "Score how well the assistant's answer satisfies the rubric."
)


@dataclass
class Judgment:
    score: float
    pass_: bool
    rationale: str
    judge_error: bool = False


def _extract_text(answer: Any) -> str:
    """Flatten an answer payload (string, list of parts, or dict) to text."""
    if isinstance(answer, str):
        return answer
    if isinstance(answer, list):
        parts = []
        for part in answer:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        return "".join(parts)
    if isinstance(answer, dict):
        return json.dumps(answer, sort_keys=True)
    return str(answer)


def _parse_json_content(content: Any) -> dict[str, Any]:
    """Parse a judge response whose `.content` may be str, dict, or a list of parts."""
    if isinstance(content, list):
        content = "".join(
            str(p.get("text", "")) if isinstance(p, dict) else str(p)
            for p in content
        )
    if not isinstance(content, str):
        content = json.dumps(content)
    content = _FENCE_RE.sub("", content).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = content[start : end + 1]
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("judge response is not a JSON object")
    return data


def _tool_use_observed(text: Any) -> bool:
    lowered = _extract_text(text).lower()
    return any(marker in lowered for marker in _TOOL_MARKERS)


def check_golden(answer: Any, expected: Any) -> bool:
    """Compare an answer to a golden snapshot, normalizing whitespace.

    JSON-typed expectations (dict/list) are parsed from a string answer
    before comparison so key order does not matter.
    """
    if isinstance(expected, (dict, list)):
        if isinstance(answer, str):
            try:
                answer = json.loads(answer)
            except ValueError:
                return False
        return answer == expected
    if isinstance(answer, (dict, list)):
        return False
    return " ".join(_extract_text(answer).split()) == " ".join(_extract_text(expected).split())


class Judge:
    def __init__(self, claude: Any = None, model: str | None = None) -> None:
        self.claude = claude
        self.model = model
        if self.model is None and claude is not None:
            self.model = getattr(claude, "model", None)

    async def judge(
        self,
        question: str,
        answer: Any,
        rubric: list[str],
        transcript: str = "",
    ) -> Judgment:
        """Score an answer against a rubric, never raising on failure."""
        if self.claude is None:
            return self._heuristic(question, answer, rubric, transcript)
        try:
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt(question, answer, rubric, transcript)},
            ]
            result = await self.claude.chat(
                messages,
                response_format={"type": "json_object"},
            )
            data = _parse_json_content(getattr(result, "content", ""))
            score = max(0.0, min(1.0, float(data.get("score", 0.0))))
            passed = bool(data.get("pass", False))
            rationale = str(data.get("rationale", ""))
            return Judgment(score=score, pass_=passed, rationale=rationale, judge_error=False)
        except Exception as exc:
            logger.warning("judge failed: %s", exc)
            return Judgment(score=0.0, pass_=False, rationale=f"judge_error: {exc}", judge_error=True)

    def _heuristic(self, question: str, answer: Any, rubric: list[str], transcript: str) -> Judgment:
        text = _extract_text(answer)
        words = text.split()
        if not words:
            return Judgment(score=0.0, pass_=False, rationale="heuristic: empty answer")
        expects_tool = any("tool" in r.lower() for r in rubric)
        if expects_tool:
            combined = f"{transcript} {text}"
            if not _tool_use_observed(combined):
                return Judgment(score=0.0, pass_=False, rationale="heuristic: expected tool use not observed")
        length_score = min(1.0, len(words) / 50.0)
        score = round(min(1.0, 0.5 + 0.5 * length_score), 2)
        return Judgment(
            score=score,
            pass_=score >= 0.5,
            rationale=f"heuristic: {len(words)} words, length score {score:.2f}",
        )

    @staticmethod
    def _user_prompt(question: str, answer: Any, rubric: list[str], transcript: str) -> str:
        parts = [
            f"QUESTION:\n{question}",
            f"ANSWER:\n{_extract_text(answer)}",
            "RUBRIC (pass requires satisfying all items):",
            *[f"- {item}" for item in rubric],
        ]
        if transcript:
            parts.append(f"TRANSCRIPT:\n{transcript}")
        return "\n\n".join(parts)
