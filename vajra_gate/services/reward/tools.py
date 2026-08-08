from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vajra_gate.services.reward.engine import NishkamaRewardSystem


def eval_tool_call(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    valid = ctx.get("valid_args", True) is not False
    return {
        "nishkama": engine._nishkama(ctx, base=0.3),
        "yoga": engine._yoga(ctx, base=0.5 if valid else -0.3),
        "guna_karma": engine._guna_karma(ctx, base=0.5 if valid else -0.3),
        "akarma": engine._akarma(ctx, base=0.2),
        "uddhara": engine._uddhara(ctx, base=0.1),
        "shanti": engine._shanti(ctx, base=0.3),
        "samaarpana": engine._samaarpana(ctx, base=0.2),
    }


def eval_tool_result(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    success = ctx.get("success", True) is not False
    return {
        "nishkama": engine._nishkama(ctx, base=0.3 if success else 0.1),
        "yoga": engine._yoga(ctx, base=0.5 if success else 0.1),
        "guna_karma": engine._guna_karma(ctx, base=0.3 if success else -0.2),
        "akarma": engine._akarma(ctx, base=0.3),
        "uddhara": engine._uddhara(ctx, base=0.2 if success else 0.0),
        "shanti": engine._shanti(ctx, base=0.3 if success else 0.1),
        "samaarpana": engine._samaarpana(ctx, base=0.3),
    }
