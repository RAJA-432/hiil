from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from vajra_gate.models import (
    RewardListResponse,
    RewardMetricsResponse,
    RewardRecordRequest,
    RewardRecordResponse,
)
from vajra_gate.services.reward import get_tracker

logger = logging.getLogger("vajra_gate")

router = APIRouter()


@router.post("/api/rewards", response_model=RewardRecordResponse)
async def record_reward(req: RewardRecordRequest):
    """Record a reward event for an action.

    The reward system evaluates the action across seven dimensions
    rooted in the Bhagavad Gita: nishkama (2:47, detached action),
    yoga (2:50, skill in action), guna_karma (4:13, quality & action),
    akarma (4:18, inaction in action), uddhara (6:5, self-upliftment),
    shanti (12:15, not agitating), samaarpana (18:66, surrender).
    """
    try:
        tracker = get_tracker()
        event = tracker.record(
            session_id=req.session_id,
            action_type=req.action_type,
            context=req.context,
            evaluate=True,
        )
        return RewardRecordResponse(
            event_id=event.event_id,
            session_id=event.session_id,
            action_type=event.action_type,
            scores=event.scores,
            total=round(event.total, 4),
            timestamp=event.timestamp,
        )
    except Exception:
        logger.exception("Failed to record reward")
        raise HTTPException(status_code=500, detail="Failed to record reward")


@router.get("/api/rewards/metrics", response_model=RewardMetricsResponse)
async def get_reward_metrics(since: str | None = Query(None, description="ISO timestamp filter")):
    """Get aggregated reward metrics across all sessions."""
    try:
        tracker = get_tracker()
        metrics = tracker.get_metrics(since=since)
        return RewardMetricsResponse(**metrics)
    except Exception:
        logger.exception("Failed to get reward metrics")
        raise HTTPException(status_code=500, detail="Failed to get reward metrics")


@router.get("/api/rewards", response_model=RewardListResponse)
async def list_rewards(
    session_id: str | None = Query(None),
    action_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """List reward events with optional filters."""
    try:
        tracker = get_tracker()
        events = tracker.list_events(
            session_id=session_id,
            action_type=action_type,
            limit=limit,
        )
        return RewardListResponse(events=events, total=len(events))
    except Exception:
        logger.exception("Failed to list rewards")
        raise HTTPException(status_code=500, detail="Failed to list rewards")
