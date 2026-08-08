from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vajra_gate.services.reward.engine import NishkamaRewardSystem


def eval_response(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    has_content = bool(ctx.get("content", "").strip())

    return {
        "nishkama": engine._nishkama(ctx, base=0.4 if has_content else -0.2),
        "yoga": engine._yoga(ctx, base=0.5 if has_content else -0.3),
        "guna_karma": engine._guna_karma(ctx, base=0.3 if has_content else -0.2),
        "akarma": engine._akarma(ctx, base=0.2),
        "uddhara": engine._uddhara(ctx, base=0.2 if has_content else -0.1),
        "shanti": engine._shanti(ctx, base=0.4 if has_content else 0.0),
        "samaarpana": engine._samaarpana(ctx, base=0.2),
    }
