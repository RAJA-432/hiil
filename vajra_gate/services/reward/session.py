from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vajra_gate.services.reward.events import REWARD_DIMENSIONS

if TYPE_CHECKING:
    from vajra_gate.services.reward.engine import NishkamaRewardSystem


def eval_session_start(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
    return {dim: 0.0 for dim in REWARD_DIMENSIONS}


def eval_session_end(ctx: dict[str, Any], engine: NishkamaRewardSystem) -> dict[str, float]:
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
