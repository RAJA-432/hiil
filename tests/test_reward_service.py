from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.gate_helpers import FakeStore
from vajra_gate.services.reward import (
    DEFAULT_WEIGHTS,
    REWARD_DIMENSIONS,
    NishkamaRewardSystem,
    RewardEvent,
    RewardTracker,
)
from vajra_gate.store import KVStore


class TestRewardEvent:
    def test_to_dict_shape(self):
        event = RewardEvent("session_1", "response", {"content": "hi"}, event_id="evt_1")
        data = event.to_dict()
        assert data["event_id"] == "evt_1"
        assert data["session_id"] == "session_1"
        assert data["action_type"] == "response"
        assert data["scores"] == {}
        assert data["total"] == 0.0

    def test_context_defaults_to_empty_dict(self):
        event = RewardEvent("s1", "error")
        assert event.context == {}


class TestNishkamaRewardSystem:
    def _evaluate(self, action_type: str, ctx: dict | None = None) -> RewardEvent:
        system = NishkamaRewardSystem()
        event = RewardEvent("session_1", action_type, ctx or {})
        return system.evaluate(event)

    def test_response_with_content_scores_positive(self):
        event = self._evaluate("response", {"content": "a helpful answer"})
        assert all(-1.0 <= v <= 1.0 for v in event.scores.values())
        assert event.scores["yoga"] > 0
        assert event.total > 0

    def test_error_unhandled_scores_negative(self):
        event = self._evaluate("error", {"error": "boom", "handled_gracefully": False})
        assert event.scores["nishkama"] < 0
        assert event.scores["shanti"] < 0
        assert event.total < 0

    def test_error_handled_gracefully_scores_positive(self):
        event = self._evaluate("error", {"error": "boom", "handled_gracefully": True, "retry_possible": True})
        assert event.scores["nishkama"] > 0
        assert event.scores["uddhara"] > 0

    def test_tool_call_valid_args(self):
        event = self._evaluate("tool_call", {"valid_args": True, "tool_name": "search"})
        assert event.scores["yoga"] > 0
        assert event.scores["guna_karma"] > 0.2

    def test_tool_call_invalid_args_penalized(self):
        event = self._evaluate("tool_call", {"valid_args": False})
        assert event.scores["yoga"] < 0
        assert event.scores["guna_karma"] < 0

    def test_refusal_legitimate_rewards_samaarpana(self):
        event = self._evaluate("refusal", {"is_legitimate_refusal": True})
        assert event.scores["samaarpana"] > 0.5

    def test_refusal_illegitimate_penalizes_samaarpana(self):
        event = self._evaluate("refusal", {"is_legitimate_refusal": False})
        assert event.scores["samaarpana"] < 0

    def test_retry_after_failure(self):
        event = self._evaluate("retry", {"success": True, "attempt": 3})
        assert event.scores["nishkama"] > 0
        assert event.scores["uddhara"] > 0

    def test_session_start_zero(self):
        event = self._evaluate("session_start")
        assert all(v == 0.0 for v in event.scores.values())

    def test_session_end_counts_messages(self):
        event = self._evaluate("session_end", {"message_count": 5})
        assert event.scores["guna_karma"] == 0.2
        assert event.scores["samaarpana"] == 0.2

    def test_unknown_action_scores_zero(self):
        event = self._evaluate("some_unknown_action")
        assert all(v == 0.0 for v in event.scores.values())
        assert event.total == 0.0

    def test_scores_clamped_to_unit_range(self):
        system = NishkamaRewardSystem()
        event = RewardEvent("s1", "response", {"content": "hi"})
        event.scores = {d: 5.0 for d in REWARD_DIMENSIONS}
        system.evaluate(event)
        assert all(v <= 1.0 for v in event.scores.values())

    def test_custom_weights_shift_total(self):
        system = NishkamaRewardSystem(weights={"nishkama": 10.0})
        event = RewardEvent("s1", "response", {"content": "hi"})
        system.evaluate(event)
        assert event.scores["nishkama"] > 0
        assert event.total > 0

    def test_default_weights_covers_all_dimensions(self):
        assert set(DEFAULT_WEIGHTS) == set(REWARD_DIMENSIONS)


class TestRewardTracker:
    def _make_tracker(self, store: FakeStore) -> RewardTracker:
        with patch("vajra_gate.store.get_store", return_value=store):
            return RewardTracker()

    def test_record_persists_and_evaluates(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        event = tracker.record("session_1", "response", {"content": "hello"})

        assert event.total > 0
        stored = store.get("rewards", event.event_id)
        assert stored["value"]["session_id"] == "session_1"
        assert stored["value"]["total"] == round(event.total, 4)

    def test_record_without_evaluation_keeps_zero_scores(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        event = tracker.record("session_1", "response", {"content": "hello"}, evaluate=False)

        assert event.scores == {}
        assert event.total == 0.0

    def test_record_batch_evaluates_all(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        events = [RewardEvent("s1", "response", {"content": "a"}), RewardEvent("s1", "tool_call", {"valid_args": True})]
        results = tracker.record_batch(events)

        assert all(e.total != 0.0 for e in results)

    def test_get_event(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        event = tracker.record("s1", "response", {"content": "hi"})

        assert tracker.get_event(event.event_id)["value"]["action_type"] == "response"
        assert tracker.get_event("missing") is None

    def test_list_events_filters_by_session(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        tracker.record("s1", "response", {"content": "a"})
        tracker.record("s2", "response", {"content": "b"})

        events = tracker.list_events(session_id="s1")
        assert len(events) == 1
        assert events[0]["value"]["session_id"] == "s1"

    def test_list_events_filters_by_action_type(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        tracker.record("s1", "response", {"content": "a"})
        tracker.record("s1", "error", {"error": "x"})

        events = tracker.list_events(action_type="error")
        assert len(events) == 1
        assert events[0]["value"]["action_type"] == "error"

    def test_get_metrics_empty(self):
        tracker = self._make_tracker(FakeStore())
        metrics = tracker.get_metrics()
        assert metrics["total_events"] == 0
        assert metrics["average_total"] == 0.0
        assert metrics["action_type_counts"] == {}

    def test_get_metrics_aggregates(self):
        store = FakeStore()
        tracker = self._make_tracker(store)
        tracker.record("s1", "response", {"content": "a"})
        tracker.record("s1", "error", {"error": "x", "handled_gracefully": False})

        metrics = tracker.get_metrics()
        assert metrics["total_events"] == 2
        assert metrics["action_type_counts"] == {"response": 1, "error": 1}
        assert set(metrics["dimension_averages"]) == set(REWARD_DIMENSIONS)
        assert all(-1.0 <= v <= 1.0 for v in metrics["dimension_averages"].values())
        assert pytest.approx(metrics["average_total"]) == metrics["average_total"]


class TestRewardStorePersistence:
    def test_jsonl_append_then_snapshot_roundtrip(self, tmp_path):
        store = KVStore(tmp_path)
        for i in range(5):
            store.upsert("rewards", [{"key": f"evt{i}", "value": {"total": i}}])

        raw = (tmp_path / "rewards.jsonl").read_text(encoding="utf-8")
        assert raw.count("\n") == 5

        store._write_rewards(store._load("rewards"))
        store.upsert("rewards", [{"key": "evt9", "value": {"total": 9}}])

        reloaded = KVStore(tmp_path)._load("rewards")
        assert len(reloaded) == 6
        assert reloaded["evt9"]["value"]["total"] == 9
        assert all(reloaded[f"evt{i}"]["value"]["total"] == i for i in range(5))

    def test_rewards_readable_after_compaction_threshold(self, tmp_path):
        import vajra_gate.store as store_module

        store = KVStore(tmp_path)
        store.upsert("rewards", [{"key": "small", "value": {"total": 1}}])
        store_module._REWARDS_COMPACT_THRESHOLD = 1
        store.upsert("rewards", [{"key": "big", "value": {"x": "y" * 10000}}])
        store_module._REWARDS_COMPACT_THRESHOLD = 1024 * 1024

        reloaded = KVStore(tmp_path)._load("rewards")
        assert reloaded["big"]["value"]["x"] == "y" * 10000
        assert reloaded["small"]["value"]["total"] == 1

    def test_corrupt_store_file_recovered(self, tmp_path):
        store = KVStore(tmp_path)
        (tmp_path / "test.json").write_text("{not valid json", encoding="utf-8")

        assert store._load("test") == {}
        assert (tmp_path / "test.json.corrupt").exists()

        store.upsert("test", [{"key": "k", "value": {"a": 1}}])
        assert store.get("test", "k")["value"]["a"] == 1
        assert store._load("test")["k"]["value"]["a"] == 1

    def test_all_items_returns_full_log_without_cap(self, tmp_path):
        store = KVStore(tmp_path)
        for i in range(3):
            store.upsert("rewards", [{"key": f"evt{i}", "value": {"total": i}}])

        items = store.all_items("rewards")
        assert sorted(item["key"] for item in items) == ["evt0", "evt1", "evt2"]
