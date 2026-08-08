from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vajra_gate.services.reward.engine import NishkamaRewardSystem


def eval_feedback(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    """User gave explicit feedback (like/dislike) on a response."""
    rating = ctx.get("rating", 0)
    liked = rating == 1
    disliked = rating == -1
    was_helpful = ctx.get("was_helpful", liked)

    return {
        "nishkama": engine._nishkama(ctx, base=0.0),
        "yoga": engine._yoga(ctx, base=0.3 if liked else (-0.1 if disliked else 0.0)),
        "guna_karma": engine._guna_karma(ctx, base=0.1),
        "akarma": engine._akarma(ctx, base=0.0),
        "uddhara": engine._uddhara(ctx, base=0.5 if liked else (-0.3 if disliked else 0.0)),
        "shanti": engine._shanti(ctx, base=0.2 if was_helpful else (-0.2 if disliked else 0.0)),
        "samaarpana": engine._samaarpana(ctx, base=0.3 if was_helpful else (-0.2 if disliked else 0.0)),
    }
