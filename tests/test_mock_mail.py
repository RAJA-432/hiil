from __future__ import annotations

import json

import setu_bridge.mock_mail as mm


async def test_list_drafts_missing_read_does_not_crash(monkeypatch) -> None:
    monkeypatch.setattr(mm, "_AUTH_TOKEN", "token")
    monkeypatch.setattr(mm, "_DRAFTS", [
        {
            "id": "d1",
            "from": "a@b.c",
            "to": "x@y.z",
            "subject": "s",
            "body": "b",
            "status": "draft",
            "folder": "drafts",
            "timestamp": "2026-08-04T00:00:00Z",
        },
    ])

    result = json.loads(await mm.list_messages(folder="drafts"))

    assert result[0]["read"] is False


async def test_send_draft_rejects_when_drafts_at_capacity(monkeypatch) -> None:
    monkeypatch.setattr(mm, "_AUTH_TOKEN", "token")
    monkeypatch.setattr(mm, "_DRAFTS", [
        {"id": f"d{i}", "from": "a@b.c", "to": "x@y.z", "subject": "s", "body": "b", "timestamp": "t"}
        for i in range(mm._MAX_DRAFTS)
    ])

    result = json.loads(await mm.send_draft(to="a@b.c", subject="hi", body="body"))

    assert result["status"] == "error"
    assert "capacity" in result["error"]


async def test_save_draft_rejects_when_drafts_at_capacity(monkeypatch) -> None:
    monkeypatch.setattr(mm, "_AUTH_TOKEN", "token")
    monkeypatch.setattr(mm, "_DRAFTS", [
        {"id": f"d{i}", "from": "a@b.c", "to": "x@y.z", "subject": "s", "body": "b", "timestamp": "t"}
        for i in range(mm._MAX_DRAFTS)
    ])

    result = json.loads(await mm.save_draft(to="a@b.c", subject="hi", body="body"))

    assert result["status"] == "error"
    assert "capacity" in result["error"]


async def test_drafts_still_append_under_capacity(monkeypatch) -> None:
    monkeypatch.setattr(mm, "_AUTH_TOKEN", "token")
    monkeypatch.setattr(mm, "_DRAFTS", [])

    await mm.save_draft(to="a@b.c", subject="hi", body="body")

    assert len(mm._DRAFTS) == 1
    listed = json.loads(await mm.list_messages(folder="drafts"))
    assert listed[0]["read"] is False
