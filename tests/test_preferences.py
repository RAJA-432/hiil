from __future__ import annotations

import pytest

from vajra_gate.services.preferences import UserPreferencesStore
from veda_engine.tools.preferences import forget, recall, remember


@pytest.fixture
def store(tmp_path):
    return UserPreferencesStore(store_dir=tmp_path)


@pytest.fixture
def tool_store(tmp_path, monkeypatch):
    from hiil_common.services.preferences import PreferencesStore

    pstore = PreferencesStore(tmp_path)
    monkeypatch.setattr("hiil_common.services.preferences.get_store", lambda: pstore)
    return pstore


class TestUserPreferencesStore:
    def test_empty_store(self, store):
        assert store.get_preferences("default") == {}
        assert store.list_keys("default") == []

    def test_set_and_get(self, store):
        store.set_preference("default", "food", "pizza")
        assert store.get_preferences("default") == {"food": "pizza"}

    def test_merge_preserves_existing_keys(self, store):
        store.set_preference("default", "a", 1)
        store.set_preference("default", "b", [1, 2, 3])
        assert store.get_preferences("default") == {"a": 1, "b": [1, 2, 3]}

    def test_set_overwrites_same_key(self, store):
        store.set_preference("default", "a", 1)
        store.set_preference("default", "a", {"x": 2})
        assert store.get_preferences("default") == {"a": {"x": 2}}

    def test_delete_preference(self, store):
        store.set_preference("default", "a", 1)
        store.set_preference("default", "b", 2)
        assert store.delete_preference("default", "a") is True
        assert store.get_preferences("default") == {"b": 2}
        assert store.delete_preference("default", "missing") is False

    def test_delete_last_preference_clears_entry(self, store):
        store.set_preference("default", "a", 1)
        assert store.delete_preference("default", "a") is True
        assert store.get_preferences("default") == {}
        assert store.list_keys("default") == []

    def test_list_keys_sorted(self, store):
        store.set_preference("default", "b", 1)
        store.set_preference("default", "a", 1)
        assert store.list_keys("default") == ["a", "b"]

    def test_arbitrary_json_values(self, store):
        store.set_preference("default", "nums", [1, 2, 3])
        store.set_preference("default", "meta", {"lang": "en", "n": 2})
        prefs = store.get_preferences("default")
        assert prefs["nums"] == [1, 2, 3]
        assert prefs["meta"] == {"lang": "en", "n": 2}

    def test_user_isolation(self, store):
        store.set_preference("alice", "food", "pizza")
        store.set_preference("bob", "food", "sushi")
        assert store.get_preferences("alice") == {"food": "pizza"}
        assert store.get_preferences("bob") == {"food": "sushi"}
        assert store.get_preferences("default") == {}

    def test_persists_across_instances(self, tmp_path):
        first = UserPreferencesStore(store_dir=tmp_path)
        first.set_preference("default", "food", "pizza")
        second = UserPreferencesStore(store_dir=tmp_path)
        assert second.get_preferences("default") == {"food": "pizza"}


class TestPreferenceTools:
    async def test_remember_recall_roundtrip(self, tool_store):
        out = await remember(preferences={"food": "pizza", "spice": "high"})
        assert "Remembered 2 preference(s)" in out
        summary = await recall()
        assert "food: pizza" in summary
        assert "spice: high" in summary

    async def test_recall_empty(self, tool_store):
        out = await recall()
        assert "No preferences stored" in out

    async def test_recall_subset(self, tool_store):
        await remember(preferences={"a": 1, "b": 2})
        out = await recall(keys=["a"])
        assert "a: 1" in out
        assert "b" not in out

    async def test_recall_missing_subset(self, tool_store):
        await remember(preferences={"a": 1})
        out = await recall(keys=["nope"])
        assert "No matching preferences" in out

    async def test_remember_merges_across_calls(self, tool_store):
        await remember(preferences={"a": 1})
        await remember(preferences={"b": 2})
        summary = await recall()
        assert "a: 1" in summary
        assert "b: 2" in summary

    async def test_forget_removes_keys(self, tool_store):
        await remember(preferences={"a": 1, "b": 2})
        out = await forget(keys=["a"])
        assert "Forgot 1 preference(s)" in out
        summary = await recall()
        assert "- a:" not in summary
        assert "b: 2" in summary

    async def test_forget_none_present(self, tool_store):
        await remember(preferences={"a": 1})
        out = await forget(keys=["nope"])
        assert "No preferences to forget" in out

    async def test_user_isolation(self, tool_store):
        await remember(user_id="alice", preferences={"food": "pizza"})
        await remember(user_id="bob", preferences={"food": "sushi"})
        assert "pizza" in await recall(user_id="alice")
        assert "sushi" in await recall(user_id="bob")
        assert "food" not in await recall(user_id="charlie")

    async def test_default_user_resolves_from_env(self, tool_store, monkeypatch):
        monkeypatch.setenv("HIIL_USER_ID", "alice")
        await remember(preferences={"food": "pizza"})
        assert tool_store.get("alice") is not None
        assert tool_store.get("default") is None

    async def test_explicit_user_id_overrides_env(self, tool_store, monkeypatch):
        monkeypatch.setenv("HIIL_USER_ID", "alice")
        await remember(user_id="bob", preferences={"food": "pizza"})
        assert tool_store.get("bob") is not None
        assert tool_store.get("alice") is None
