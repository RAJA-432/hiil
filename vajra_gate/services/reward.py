from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("vajra_gate.reward")

# ─── Seven dimensions from the Bhagavad Gita ──────────────────────
#
# 1.  nishkama  (2:47) – duty without attachment to results
# 2.  yoga      (2:50) – skill / precision in action
# 3.  guna_karma (4:13) – classification by quality and action
# 4.  akarma    (4:18) – seeing inaction in action, action in inaction
# 5.  uddhara   (6:5)  – self-upliftment
# 6.  shanti    (12:15) – not agitating, not agitated
# 7.  samaarpana (18:66) – surrender to higher wisdom / ethics

BHAGAVAD_GITA_VERSES = {
    "nishkama": {
        "chapter": 2,
        "verse": 47,
        "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
        "translation": "You have the right to perform your prescribed duty, but you are not entitled to the fruits of action. Never consider yourself the cause of the results, nor be attached to inaction.",
    },
    "yoga": {
        "chapter": 2,
        "verse": 50,
        "sanskrit": "योगः कर्मसु कौशलम्।",
        "translation": "Yoga is skill in action.",
    },
    "guna_karma": {
        "chapter": 4,
        "verse": 13,
        "sanskrit": "चातुर्वर्ण्यं मया सृष्टं गुणकर्मविभागशः।",
        "translation": "The fourfold order was created by Me according to quality and action.",
    },
    "akarma": {
        "chapter": 4,
        "verse": 18,
        "sanskrit": "कर्मण्यकर्म यः पश्येदकर्मणि च कर्म यः। स बुद्धिमान्मनुष्येषु स युक्तः कृत्स्नकर्मकृत्॥",
        "translation": "He who sees inaction in action and action in inaction is wise among men.",
    },
    "uddhara": {
        "chapter": 6,
        "verse": 5,
        "sanskrit": "उद्धरेदात्मनात्मानं नात्मानमवसादयेत्। आत्मैव ह्यात्मनो बन्धुरात्मैव रिपुरात्मनः॥",
        "translation": "Let a man lift himself by his own self alone, and not degrade himself.",
    },
    "shanti": {
        "chapter": 12,
        "verse": 15,
        "sanskrit": "यस्मान्नोद्विजते लोको लोकान्नोद्विजते च यः। हर्षामर्षभयोद्वेगैर्मुक्तो यः स च मे प्रियः॥",
        "translation": "He by whom the world is not agitated, and who is not agitated by the world, is dear to Me.",
    },
    "samaarpana": {
        "chapter": 18,
        "verse": 66,
        "sanskrit": "सर्वधर्मान्परित्यज्य मामेकं शरणं व्रज। अहं त्वां सर्वपापेभ्यो मोक्षयिष्यामि मा शुचः॥",
        "translation": "Abandon all duties and surrender unto Me alone. Fear not.",
    },
}

REWARD_DIMENSIONS = tuple(BHAGAVAD_GITA_VERSES.keys())

DEFAULT_WEIGHTS = {
    "nishkama": 1.2,
    "yoga": 1.0,
    "guna_karma": 0.8,
    "akarma": 0.7,
    "uddhara": 0.9,
    "shanti": 1.0,
    "samaarpana": 1.1,
}


class RewardEvent:
    def __init__(
        self,
        session_id: str,
        action_type: str,
        context: dict[str, Any] | None = None,
        event_id: str | None = None,
    ):
        self.event_id = event_id or uuid.uuid4().hex[:12]
        self.session_id = session_id
        self.action_type = action_type
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.context = context or {}
        self.scores: dict[str, float] = {}
        self.total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "action_type": self.action_type,
            "timestamp": self.timestamp,
            "scores": self.scores,
            "total": round(self.total, 4),
            "context": self.context,
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
        evaluator = {
            "response": self._eval_response,
            "tool_call": self._eval_tool_call,
            "tool_result": self._eval_tool_result,
            "error": self._eval_error,
            "retry": self._eval_retry,
            "refusal": self._eval_refusal,
            "feedback": self._eval_feedback,
            "session_start": self._eval_session_start,
            "session_end": self._eval_session_end,
        }.get(event.action_type, self._eval_unknown)

        scores = evaluator(event.context)
        for dim in REWARD_DIMENSIONS:
            clamped = max(-1.0, min(1.0, scores.get(dim, 0.0)))
            event.scores[dim] = clamped

        weighted = sum(
            event.scores[d] * self.weights.get(d, 1.0) for d in REWARD_DIMENSIONS
        )
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

    def _eval_feedback(self, ctx: dict[str, Any]) -> dict[str, float]:
        """User gave explicit feedback (like/dislike) on a response."""
        rating = ctx.get("rating", 0)
        liked = rating == 1
        disliked = rating == -1
        was_helpful = ctx.get("was_helpful", liked)

        return {
            "nishkama": self._nishkama(ctx, base=0.0),
            "yoga": self._yoga(ctx, base=0.3 if liked else (-0.1 if disliked else 0.0)),
            "guna_karma": self._guna_karma(ctx, base=0.1),
            "akarma": self._akarma(ctx, base=0.0),
            "uddhara": self._uddhara(ctx, base=0.5 if liked else (-0.3 if disliked else 0.0)),
            "shanti": self._shanti(ctx, base=0.2 if was_helpful else (-0.2 if disliked else 0.0)),
            "samaarpana": self._samaarpana(ctx, base=0.3 if was_helpful else (-0.2 if disliked else 0.0)),
        }

    # ─── Action-type evaluators ────────────────────────────────────

    def _eval_response(self, ctx: dict[str, Any]) -> dict[str, float]:
        has_content = bool(ctx.get("content", "").strip())

        return {
            "nishkama": self._nishkama(ctx, base=0.4 if has_content else -0.2),
            "yoga": self._yoga(ctx, base=0.5 if has_content else -0.3),
            "guna_karma": self._guna_karma(ctx, base=0.3 if has_content else -0.2),
            "akarma": self._akarma(ctx, base=0.2),
            "uddhara": self._uddhara(ctx, base=0.2 if has_content else -0.1),
            "shanti": self._shanti(ctx, base=0.4 if has_content else 0.0),
            "samaarpana": self._samaarpana(ctx, base=0.2),
        }

    def _eval_tool_call(self, ctx: dict[str, Any]) -> dict[str, float]:
        valid = ctx.get("valid_args", True) is not False
        return {
            "nishkama": self._nishkama(ctx, base=0.3),
            "yoga": self._yoga(ctx, base=0.5 if valid else -0.3),
            "guna_karma": self._guna_karma(ctx, base=0.5 if valid else -0.3),
            "akarma": self._akarma(ctx, base=0.2),
            "uddhara": self._uddhara(ctx, base=0.1),
            "shanti": self._shanti(ctx, base=0.3),
            "samaarpana": self._samaarpana(ctx, base=0.2),
        }

    def _eval_tool_result(self, ctx: dict[str, Any]) -> dict[str, float]:
        success = ctx.get("success", True) is not False
        return {
            "nishkama": self._nishkama(ctx, base=0.3 if success else 0.1),
            "yoga": self._yoga(ctx, base=0.5 if success else 0.1),
            "guna_karma": self._guna_karma(ctx, base=0.3 if success else -0.2),
            "akarma": self._akarma(ctx, base=0.3),
            "uddhara": self._uddhara(ctx, base=0.2 if success else 0.0),
            "shanti": self._shanti(ctx, base=0.3 if success else 0.1),
            "samaarpana": self._samaarpana(ctx, base=0.3),
        }

    def _eval_error(self, ctx: dict[str, Any]) -> dict[str, float]:
        handled = ctx.get("handled_gracefully", False)
        retry_possible = ctx.get("retry_possible", False)
        return {
            "nishkama": self._nishkama(ctx, base=-0.2 if not handled else 0.3),
            "yoga": self._yoga(ctx, base=0.1 if handled else -0.2),
            "guna_karma": self._guna_karma(ctx, base=0.0),
            "akarma": self._akarma(ctx, base=0.2 if handled else -0.1),
            "uddhara": self._uddhara(ctx, base=0.3 if handled and retry_possible else 0.0),
            "shanti": self._shanti(ctx, base=0.5 if handled else -0.3),
            "samaarpana": self._samaarpana(ctx, base=0.2 if handled else -0.2),
        }

    def _eval_retry(self, ctx: dict[str, Any]) -> dict[str, float]:
        success = ctx.get("success", True) is not False
        attempt = ctx.get("attempt", 1)
        return {
            "nishkama": self._nishkama(ctx, base=0.7),
            "yoga": self._yoga(ctx, base=max(0.0, 0.5 - min(attempt, 5) * 0.08)),
            "guna_karma": self._guna_karma(ctx, base=0.3 if success else 0.1),
            "akarma": self._akarma(ctx, base=0.2),
            "uddhara": self._uddhara(ctx, base=0.5 if success else 0.2),
            "shanti": self._shanti(ctx, base=0.5),
            "samaarpana": self._samaarpana(ctx, base=0.3),
        }

    def _eval_refusal(self, ctx: dict[str, Any]) -> dict[str, float]:
        legitimate = ctx.get("is_legitimate_refusal", False)
        return {
            "nishkama": self._nishkama(ctx, base=0.0),
            "yoga": self._yoga(ctx, base=0.2),
            "guna_karma": self._guna_karma(ctx, base=0.3 if legitimate else -0.2),
            "akarma": self._akarma(ctx, base=0.1),
            "uddhara": self._uddhara(ctx, base=0.1),
            "shanti": self._shanti(ctx, base=0.3 if legitimate else -0.2),
            "samaarpana": self._samaarpana(ctx, base=0.5 if legitimate else -0.5),
        }

    def _eval_session_start(self, ctx: dict[str, Any]) -> dict[str, float]:
        return {
            dim: 0.0 for dim in REWARD_DIMENSIONS
        }

    def _eval_session_end(self, ctx: dict[str, Any]) -> dict[str, float]:
        count = ctx.get("message_count", 0)
        return {
            "nishkama": 0.3,
            "yoga": 0.2,
            "guna_karma": 0.2 if count > 0 else -0.1,
            "akarma": 0.1,
            "uddhara": 0.1,
            "shanti": 0.3,
            "samaarpana": 0.2 if count > 0 else 0.0,
        }

    def _eval_unknown(self, ctx: dict[str, Any]) -> dict[str, float]:
        return {dim: 0.0 for dim in REWARD_DIMENSIONS}


class RewardTracker:
    """Persistent reward event store and metric aggregator.

    Stores individual events in ``~/.hiil/store/rewards.json`` and computed
    metrics in ``~/.hiil/store/reward_metrics.json``.
    """

    def __init__(self):
        from vajra_gate.store import get_store

        self._store = get_store()
        self._system = NishkamaRewardSystem()

    def record(
        self,
        session_id: str,
        action_type: str,
        context: dict[str, Any] | None = None,
        evaluate: bool = True,
    ) -> RewardEvent:
        event = RewardEvent(session_id, action_type, context)
        if evaluate:
            self._system.evaluate(event)
        self._persist(event)
        return event

    def record_batch(self, events: list[RewardEvent]) -> list[RewardEvent]:
        for event in events:
            self._system.evaluate(event)
            self._persist(event)
        return events

    def _persist(self, event: RewardEvent) -> None:
        self._store.upsert("rewards", [{"key": event.event_id, "value": event.to_dict()}])

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        return self._store.get("rewards", event_id)

    def list_events(
        self,
        session_id: str | None = None,
        action_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = self._store.search("rewards", limit=limit)
        if session_id:
            results = [r for r in results if r.get("value", {}).get("session_id") == session_id]
        if action_type:
            results = [r for r in results if r.get("value", {}).get("action_type") == action_type]
        return results

    def get_metrics(
        self,
        since: str | None = None,
    ) -> dict[str, Any]:
        events = self._store.search("rewards", limit=10000)
        if since:
            events = [e for e in events if e.get("value", {}).get("timestamp", "") >= since]

        if not events:
            return {
                "total_events": 0,
                "average_total": 0.0,
                "dimension_averages": {d: 0.0 for d in REWARD_DIMENSIONS},
                "action_type_counts": {},
            }

        dim_sums: dict[str, float] = {d: 0.0 for d in REWARD_DIMENSIONS}
        total_sum = 0.0
        action_counts: dict[str, int] = {}

        for entry in events:
            val = entry.get("value", {})
            scores = val.get("scores", {})
            total_sum += val.get("total", 0.0)
            for d in REWARD_DIMENSIONS:
                dim_sums[d] += scores.get(d, 0.0)
            at = val.get("action_type", "unknown")
            action_counts[at] = action_counts.get(at, 0) + 1

        count = len(events)
        return {
            "total_events": count,
            "average_total": round(total_sum / count, 4),
            "dimension_averages": {
                d: round(dim_sums[d] / count, 4) for d in REWARD_DIMENSIONS
            },
            "action_type_counts": action_counts,
        }


_GLOBAL_TRACKER: RewardTracker | None = None


def get_tracker() -> RewardTracker:
    global _GLOBAL_TRACKER
    if _GLOBAL_TRACKER is None:
        _GLOBAL_TRACKER = RewardTracker()
    return _GLOBAL_TRACKER
