from __future__ import annotations

import re
from typing import Any

from mcp_cli.services.agents.models import AgentConfig
from mcp_cli.services.agents.subagents import SUBAGENT_REGISTRY

_STOPWORDS = frozenset({
    "a", "about", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "be", "been", "but", "by", "can", "check", "could", "did", "do", "does",
    "find", "for", "from", "get", "give", "had", "has", "have", "how", "i",
    "if", "in", "into", "is", "it", "its", "list", "make", "me", "more",
    "most", "my", "need", "not", "of", "on", "or", "our", "over", "please",
    "read", "see", "show", "so", "some", "tell", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "to", "under",
    "up", "us", "use", "view", "want", "was", "we", "were", "what", "when",
    "where", "which", "why", "will", "with", "would", "you", "your",
})


def _tokens(text: str) -> list[str]:
    return [
        t
        for t in re.split(r"[^a-z0-9_]+", (text or "").lower())
        if t and t not in _STOPWORDS
    ]


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _build_hints(config: AgentConfig) -> dict[str, int]:
    """Map stemmed keyword -> weight derived from an agent's spec."""
    hints: dict[str, int] = {}

    def _add(text: str, weight: int) -> None:
        for token in _tokens(text):
            key = _stem(token)
            if key:
                hints[key] = max(hints.get(key, 0), weight)

    _add(config.name.replace("-", " "), 3)
    _add(config.role, 2)
    for capability in config.capabilities:
        _add(capability, 2)
    _add(config.system_prompt, 1)
    return hints


class RouteClassifier:
    """Decides which subagent should handle a user request.

    Rule-based classification is a fast deterministic term matcher built from
    each ``AgentConfig`` (name, role, capabilities, system prompt).  An
    optional LLM-backed path returns a single agent name via a tiny prompt and
    degrades gracefully to ``None`` when the model is unavailable.
    """

    def __init__(self, registry: dict[str, AgentConfig] = SUBAGENT_REGISTRY):
        self.registry = registry
        self._hints = {name: _build_hints(config) for name, config in registry.items()}

    def classify_rule_based(self, request: str) -> str | None:
        if not request:
            return None
        request_tokens = {_stem(t) for t in _tokens(request)}
        best_name: str | None = None
        best_score = 0
        for name, hints in self._hints.items():
            score = sum(weight for keyword, weight in hints.items() if keyword in request_tokens)
            if score > best_score:
                best_name, best_score = name, score
        return best_name if best_score > 0 else None

    async def classify_with_model(self, request: str, llm_client: Any) -> str | None:
        if llm_client is None or not request:
            return None
        names = list(self.registry)
        prompt = (
            "You are an intent router. Choose the single most appropriate agent "
            f"from this list: {', '.join(names)}. "
            "Reply with exactly one agent name, or 'none' (or 'orchestrator') "
            "if no agent fits the request."
        )
        try:
            response = await llm_client.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": request},
            ])
        except Exception:
            return None
        text = (getattr(response, "content", "") or "").strip().lower()
        for name in names:
            if name in text:
                return name
        return None

    async def classify(self, request: str, llm_client: Any | None = None) -> str | None:
        if llm_client is not None:
            return await self.classify_with_model(request, llm_client)
        return self.classify_rule_based(request)


def classify_rule_based(
    request: str,
    registry: dict[str, AgentConfig] = SUBAGENT_REGISTRY,
) -> str | None:
    return RouteClassifier(registry).classify_rule_based(request)


async def classify_with_model(
    request: str,
    llm_client: Any,
    registry: dict[str, AgentConfig] = SUBAGENT_REGISTRY,
) -> str | None:
    return await RouteClassifier(registry).classify_with_model(request, llm_client)


async def classify(
    request: str,
    llm_client: Any | None = None,
    registry: dict[str, AgentConfig] = SUBAGENT_REGISTRY,
) -> str | None:
    if llm_client is not None:
        return await classify_with_model(request, llm_client, registry=registry)
    return classify_rule_based(request, registry=registry)
