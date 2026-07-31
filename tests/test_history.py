from __future__ import annotations

import time
from datetime import datetime

import pytest

from mcp_cli.services.history import ChatHistoryManager


@pytest.fixture
def history(tmp_path) -> ChatHistoryManager:
    mgr = ChatHistoryManager(str(tmp_path / "history_test.db"), max_sessions=50)
    yield mgr
    mgr.close()


def test_session_summaries_title_and_message_count(history):
    history.save_message("sess_a", "assistant", "assistant preamble")
    history.save_message("sess_a", "user", "hello world")
    history.save_message("sess_a", "user", "second user message")
    history.save_message("sess_b", "assistant", "no user message here")

    summaries = history.session_summaries()
    by_id = {s["session_id"]: s for s in summaries}

    assert by_id["sess_a"]["title"] == "hello world"
    assert by_id["sess_a"]["message_count"] == 3
    assert by_id["sess_a"]["last_ts"] == history.load_session("sess_a")[-1]["timestamp"]
    assert by_id["sess_b"]["title"] == ""
    assert by_id["sess_b"]["message_count"] == 1


def test_session_summaries_title_full_content(history):
    long = "x" * 200
    history.save_message("sess_long", "user", long)

    summaries = history.session_summaries()

    assert len(summaries) == 1
    assert summaries[0]["title"] == long


def test_session_summaries_ordered_by_last_activity(history):
    history.save_message("sess_old", "user", "first activity")
    time.sleep(0.01)
    history.save_message("sess_new", "user", "later activity")
    time.sleep(0.01)
    history.save_message("sess_old", "assistant", "reply")

    summaries = history.session_summaries()

    assert [s["session_id"] for s in summaries] == ["sess_old", "sess_new"]
    assert summaries[0]["last_ts"] > summaries[1]["last_ts"]
    assert datetime.fromisoformat(summaries[0]["last_ts"]) is not None


def test_session_summaries_pagination(history):
    for i in range(5):
        history.save_message(f"session_{i}", "user", f"message {i}")
        time.sleep(0.01)

    page1 = history.session_summaries(limit=2, offset=0)
    page2 = history.session_summaries(limit=2, offset=2)
    page3 = history.session_summaries(limit=2, offset=4)

    assert [s["session_id"] for s in page1] == ["session_4", "session_3"]
    assert [s["session_id"] for s in page2] == ["session_2", "session_1"]
    assert [s["session_id"] for s in page3] == ["session_0"]


def test_prune_deferred_until_100_writes(tmp_path):
    mgr = ChatHistoryManager(str(tmp_path / "prune_test.db"), max_sessions=1)
    try:
        for i in range(99):
            mgr.save_message(f"session_{i}", "user", "hi")
        assert mgr._writes_since_prune == 99
        assert mgr.count_sessions() == 99

        mgr.save_message("session_99", "user", "hi")
        assert mgr._writes_since_prune == 0
        assert mgr.count_sessions() == 1
    finally:
        mgr.close()


def test_max_sessions_still_enforced_after_throttle(tmp_path):
    mgr = ChatHistoryManager(str(tmp_path / "enforce_test.db"), max_sessions=2)
    try:
        for i in range(100):
            mgr.save_message(f"session_{i}", "user", "hi")
        assert mgr._writes_since_prune == 0
        assert mgr.count_sessions() == 2
    finally:
        mgr.close()


async def test_async_session_summaries(tmp_path):
    mgr = ChatHistoryManager(str(tmp_path / "async_test.db"), max_sessions=50)
    try:
        mgr.save_message("sess_async", "user", "hello")

        summaries = await mgr.async_session_summaries()

        assert len(summaries) == 1
        assert summaries[0]["session_id"] == "sess_async"
        assert summaries[0]["title"] == "hello"
        assert summaries[0]["message_count"] == 1
    finally:
        mgr.close()
