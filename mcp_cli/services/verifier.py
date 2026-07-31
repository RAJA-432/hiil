from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_CRITIQUE_SYSTEM_PROMPT = (
    "You are a rigorous answer verifier. Given a user question, optional reference "
    "context, optional tool results, and an assistant answer, evaluate the answer for: "
    "factual consistency with the provided context, relevance to the user's question, "
    "hallucination (claims unsupported by the context or tool results), and completeness. "
    'Respond with STRICT JSON only, with no prose, in exactly this shape: '
    '{"valid": bool, "score": 0.0-1.0 float, "issues": [string], "revised": string or null}. '
    '"valid" is true when the answer is acceptable. "score" rates the overall quality of '
    'the answer. "issues" lists concrete problems found, or an empty list when none exist. '
    '"revised" is a corrected answer when the answer needs revision, otherwise null.'
)


@dataclass(frozen=True)
class Verdict:
    valid: bool
    score: float
    issues: list[str]
    revised: str | None


_FAILSOFT_VERDICT = Verdict(valid=True, score=1.0, issues=[], revised=None)


class Verifier:
    def __init__(self, claude: Any, *, model: str | None = None) -> None:
        self.claude = claude
        self.model = model or claude.model

    async def verify(
        self,
        answer: str,
        user_input: str,
        rag_context: str = "",
        tool_summary: str = "",
    ) -> Verdict:
        try:
            messages = [
                {"role": "system", "content": _CRITIQUE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _format_input(answer, user_input, rag_context, tool_summary),
                },
            ]
            response = await self.claude.chat(messages, response_format={"type": "json_object"})
            payload = _parse_json(_extract_content(response))
            return _verdict_from(payload)
        except Exception as exc:
            logger.warning("verifier degraded to pass-through: %s", exc)
            return _FAILSOFT_VERDICT


def _format_input(answer: str, user_input: str, rag_context: str, tool_summary: str) -> str:
    parts = [f"User question:\n{user_input}"]
    if rag_context:
        parts.append(f"Reference context:\n{rag_context}")
    if tool_summary:
        parts.append(f"Tool results:\n{tool_summary}")
    parts.append(f"Assistant answer:\n{answer}")
    return "\n\n".join(parts)


def _extract_content(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
            elif hasattr(part, "text") and isinstance(getattr(part, "text"), str):
                parts.append(part.text)
        return "\n".join(parts)
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    return ""


def _parse_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        fenced = raw.split("```", 2)
        if len(fenced) >= 2:
            candidate = fenced[1].strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate:
                raw = candidate
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in verifier response")
    return json.loads(raw[start : end + 1])


def _verdict_from(payload: dict[str, Any]) -> Verdict:
    if not isinstance(payload, dict):
        raise ValueError("verifier payload must be a JSON object")
    valid = payload.get("valid")
    score = payload.get("score")
    if not isinstance(valid, bool):
        raise ValueError("verifier payload missing boolean 'valid'")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("verifier payload missing numeric 'score'")
    issues_raw = payload.get("issues")
    if isinstance(issues_raw, list):
        issues = [str(item) for item in issues_raw if not isinstance(item, bool)]
    else:
        issues = []
    revised_raw = payload.get("revised")
    revised = revised_raw if isinstance(revised_raw, str) and revised_raw.strip() else None
    return Verdict(
        valid=valid,
        score=min(1.0, max(0.0, float(score))),
        issues=issues,
        revised=revised,
    )
