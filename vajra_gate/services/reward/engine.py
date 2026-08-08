from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vajra_gate.services.reward.errors import eval_error, eval_refusal, eval_retry, eval_unknown
from vajra_gate.services.reward.events import DEFAULT_WEIGHTS, REWARD_DIMENSIONS, RewardEvent
from vajra_gate.services.reward.feedback import eval_feedback
from vajra_gate.services.reward.response import eval_response
from vajra_gate.services.reward.session import eval_session_end, eval_session_start
from vajra_gate.services.reward.tools import eval_tool_call, eval_tool_result

_Evaluator = Callable[[dict[str, Any], "NishkamaRewardSystem"], dict[str, float]]

_EVALUATORS: dict[str, _Evaluator] = {
    "response": eval_response,
    "tool_call": eval_tool_call,
    "tool_result": eval_tool_result,
    "error": eval_error,
    "retry": eval_retry,
    "refusal": eval_refusal,
    "feedback": eval_feedback,
    "session_start": eval_session_start,
    "session_end": eval_session_end,
}


class NishkamaRewardSystem:
    """Reinforcement learning reward system rooted in the Bhagavad Gita.

    Every AI action is evaluated across seven dimensions, each reflecting a
    core teaching from the Gita.  Scores range [-1.0, 1.0]: positive means
    the action aligns with the teaching, negative means it violates it.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def evaluate(self, event: RewardEvent) -> RewardEvent:
        evaluator = _EVALUATORS.get(event.action_type, eval_unknown)
        scores = evaluator(event.context, self)

        for dim in REWARD_DIMENSIONS:
            clamped = max(-1.0, min(1.0, scores.get(dim, 0.0)))
            event.scores[dim] = clamped

        weighted = sum(event.scores[d] * self.weights.get(d, 1.0) for d in REWARD_DIMENSIONS)
        total_weight = sum(self.weights.get(d, 1.0) for d in REWARD_DIMENSIONS)
        event.total = weighted / total_weight if total_weight else 0.0
        return event

    # ─── Verse 2:47 — Nishkama Karma: detached action ───────────────

    def _nishkama(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward detachment from outcomes; penalise attachment/frustration."""
        score = base
        if ctx.get("error"):
            if ctx.get("handled_gracefully"):
                score += 0.4
            else:
                score -= 0.3
        if ctx.get("is_retry"):
            score += 0.3
        if ctx.get("frustration"):
            score -= 0.5
        if ctx.get("blames_external"):
            score -= 0.4
        return score

    # ─── Verse 2:50 — Yoga: skill in action ─────────────────────────

    def _yoga(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward precision, efficiency, and mastery."""
        score = base
        if ctx.get("valid_args") is False:
            score -= 0.3
        if ctx.get("duration_ms", 0) > 30000:
            score -= 0.2
        if ctx.get("token_count", 0) > 0:
            score += min(0.5, ctx["token_count"] / 8192 * 0.5)
        if ctx.get("precision"):
            score += 0.2
        return score

    # ─── Verse 4:13 — Guna-Karma: classification by quality/action ──

    def _guna_karma(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward appropriate categorisation and organisation."""
        score = base
        if ctx.get("tool_name"):
            score += 0.2
        if ctx.get("correct_classification"):
            score += 0.3
        if ctx.get("misclassification"):
            score -= 0.4
        if ctx.get("organized_output"):
            score += 0.2
        return score

    # ─── Verse 4:18 — Akarma: inaction in action ────────────────────

    def _akarma(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward appropriate automation; seeing action where there is none."""
        score = base
        if ctx.get("automated_process"):
            score += 0.3
        if ctx.get("behind_the_scenes_work"):
            score += 0.2
        if ctx.get("unnecessary_action"):
            score -= 0.4
        if ctx.get("missed_optimization"):
            score -= 0.2
        return score

    # ─── Verse 6:5 — Uddhara: self-upliftment ──────────────────────

    def _uddhara(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward learning, improvement, and not degrading."""
        score = base
        if ctx.get("learning_occurred"):
            score += 0.4
        if ctx.get("self_correction"):
            score += 0.5
        if ctx.get("improvement"):
            score += 0.3
        if ctx.get("degradation"):
            score -= 0.5
        return score

    # ─── Verse 12:15 — Shanti: not agitating, not agitated ──────────

    def _shanti(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward calmness, impartiality; penalise agitation."""
        score = base
        if ctx.get("handled_gracefully"):
            score += 0.3
        if ctx.get("calm_response"):
            score += 0.3
        if ctx.get("bias"):
            score -= 0.5
        if ctx.get("agitation"):
            score -= 0.4
        if ctx.get("impartial"):
            score += 0.2
        return score

    # ─── Verse 18:66 — Samaarpana: surrender to higher wisdom ───────

    def _samaarpana(self, ctx: dict[str, Any], base: float = 0.0) -> float:
        """Reward ethical alignment and knowing one's limits."""
        score = base
        if ctx.get("ethical_refusal"):
            score += 0.5
        if ctx.get("is_legitimate_refusal"):
            score += 0.3
        if ctx.get("harmful_action"):
            score -= 0.7
        if ctx.get("exceeded_authority"):
            score -= 0.5
        if ctx.get("deferred_to_human"):
            score += 0.4
        return score
