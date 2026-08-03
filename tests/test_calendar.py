from __future__ import annotations

import json

import pytest

import setu_bridge.calendar as calendar


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = calendar._CalendarStore(tmp_path / "calendar.json")
    monkeypatch.setattr(calendar, "_store", s)
    monkeypatch.delenv("HIIL_USER_ID", raising=False)
    return s


async def test_create_and_list_roundtrip_isolation_by_user(store):
    created = json.loads(await calendar.create_event(
        title="Standup", date="2026-12-31", start_time="10:00", user_id="alice"
    ))
    assert created["status"] == "created"

    listed = json.loads(await calendar.list_events(date="2026-12-31", user_id="alice"))
    assert listed["count"] == 1
    assert listed["events"][0]["title"] == "Standup"

    other = json.loads(await calendar.list_events(date="2026-12-31", user_id="bob"))
    assert other["count"] == 0

    upcoming = json.loads(await calendar.list_events(user_id="alice"))
    assert upcoming["count"] == 1


async def test_update_changes_fields_and_delete_removes(store):
    created = json.loads(await calendar.create_event(
        title="Review", date="2026-12-31", start_time="14:00", location="Room A", user_id="alice"
    ))
    event_id = created["event"]["id"]

    updated = json.loads(await calendar.update_event(
        event_id, title="Review v2", start_time="15:00", location="Room B", user_id="alice"
    ))
    assert updated["status"] == "updated"
    assert updated["event"]["title"] == "Review v2"
    assert updated["event"]["start_time"] == "15:00"
    assert updated["event"]["location"] == "Room B"
    assert updated["event"]["date"] == "2026-12-31"

    listed = json.loads(await calendar.list_events(date="2026-12-31", user_id="alice"))
    assert listed["count"] == 1
    assert listed["events"][0]["title"] == "Review v2"

    deleted = json.loads(await calendar.delete_event(event_id, user_id="alice"))
    assert deleted["status"] == "deleted"

    listed = json.loads(await calendar.list_events(date="2026-12-31", user_id="alice"))
    assert listed["count"] == 0


async def test_free_slots_do_not_overlap_existing_events(store):
    await calendar.create_event(
        title="Busy block", date="2026-08-03", start_time="10:00", duration_min=60, user_id="alice"
    )
    result = await calendar.free_slots(
        date="2026-08-03", from_time="09:00", to_time="12:00", duration_min=60, user_id="alice"
    )
    assert "- 09:00 - 10:00" in result
    assert "- 11:00 - 12:00" in result

    busy = (600, 660)
    for line in result.splitlines():
        if not line.startswith("- ") or "- none" in line:
            continue
        start_s, end_s = line[2:].split(" - ")
        start = int(start_s[:2]) * 60 + int(start_s[3:])
        end = int(end_s[:2]) * 60 + int(end_s[3:])
        assert end <= busy[0] or start >= busy[1], f"window {start}-{end} overlaps busy {busy}"


async def test_bad_date_format_raises_clear_error(store):
    with pytest.raises(ValueError, match="Invalid date 'not-a-date'"):
        await calendar.list_events(date="not-a-date", user_id="alice")
    with pytest.raises(ValueError, match="Invalid date '31/12/2026'"):
        await calendar.create_event(title="x", date="31/12/2026", user_id="alice")
    with pytest.raises(ValueError, match="Invalid time '25:00'"):
        await calendar.free_slots(date="2026-08-03", from_time="25:00", user_id="alice")


async def test_persistence_survives_fresh_instance(store, tmp_path):
    await calendar.create_event(
        title="Persisted", date="2026-12-31", start_time="09:00", user_id="alice"
    )

    fresh = calendar._CalendarStore(tmp_path / "calendar.json")
    events = fresh.events_for("alice")
    assert len(events) == 1
    assert events[0]["title"] == "Persisted"
    assert events[0]["date"] == "2026-12-31"
