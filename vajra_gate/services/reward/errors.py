from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vajra_gate.services.reward.events import REWARD_DIMENSIONS

if TYPE_CHECKING:
    from vajra_gate.services.reward.engine import NishkamaRewardSystem


def eval_error(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    handled = ctx.get("handled_gracefully", False)
    retry_possible = ctx.get("retry_possible", False)
    return {
        "nishkama": engine._nishkama(ctx, base=-0.2 if not handled else 0.3),
        "yoga": engine._yoga(ctx, base=0.1 if handled else -0.2),
        "guna_karma": engine._guna_karma(ctx, base=0.0),
        "akarma": engine._akarma(ctx, base=0.2 if handled else -0.1),
        "uddhara": engine._uddhara(ctx, base=0.3 if handled and retry_possible else 0.0),
        "shanti": engine._shanti(ctx, base=0.5 if handled else -0.3),
        "samaarpana": engine._samaarpana(ctx, base=0.2 if handled else -0.2),
    }


def eval_retry(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    success = ctx.get("success", True) is not False
    attempt = ctx.get("attempt", 1)
    return {
        "nishkama": engine._nishkama(ctx, base=0.7),
        "yoga": engine._yoga(ctx, base=max(0.0, 0.5 - min(attempt, 5) * 0.08)),
        "guna_karma": engine._guna_karma(ctx, base=0.3 if success else 0.1),
        "akarma": engine._akarma(ctx, base=0.2),
        "uddhara": engine._uddhara(ctx, base=0.5 if success else 0.2),
        "shanti": engine._shanti(ctx, base=0.5),
        "samaarpana": engine._samaarpana(ctx, base=0.3),
    }


def eval_refusal(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    legitimate = ctx.get("is_legitimate_refusal", False)
    return {
        "nishkama": engine._nishkama(ctx, base=0.0),
        "yoga": engine._yoga(ctx, base=0.2),
        "guna_karma": engine._guna_karma(ctx, base=0.3 if legitimate else -0.2),
        "akarma": engine._akarma(ctx, base=0.1),
        "uddhara": engine._uddhara(ctx, base=0.1),
        "shanti": engine._shanti(ctx, base=0.3 if legitimate else -0.2),
        "samaarpana": engine._samaarpana(ctx, base=0.5 if legitimate else -0.5),
    }


def eval_unknown(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    return {dim: 0.0 for dim in REWARD_DIMENSIONS}
