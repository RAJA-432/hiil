from __future__ import annotations

from typing import Any

from vajra_gate.services.reward.engine import NishkamaRewardSystem
from vajra_gate.services.reward.events import REWARD_DIMENSIONS, RewardEvent


class RewardTracker:
    """Persistent reward event store and metric aggregator.

    Stores individual events as an append-only JSONL log in
    ``~/.hiil/store/rewards.jsonl``; metrics are computed on the fly.
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
        events = self._store.all_items("rewards")
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
            "dimension_averages": {d: round(dim_sums[d] / count, 4) for d in REWARD_DIMENSIONS},
            "action_type_counts": action_counts,
        }


_GLOBAL_TRACKER: RewardTracker | None = None


def get_tracker() -> RewardTracker:
    global _GLOBAL_TRACKER
    if _GLOBAL_TRACKER is None:
        _GLOBAL_TRACKER = RewardTracker()
    return _GLOBAL_TRACKER
