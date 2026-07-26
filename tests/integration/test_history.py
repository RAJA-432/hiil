import pytest

from mcp_cli.services.history import ChatHistoryManager


@pytest.fixture
def history(tmp_path):
    db_path = str(tmp_path / "chat_history.db")
    h = ChatHistoryManager(db_path, max_sessions=3)
    yield h
    h.close()

@pytest.mark.asyncio
async def test_save_and_load(history):
    history.save_message("sess1", "user", "hello")
    history.save_message("sess1", "assistant", "hi there")
    msgs = history.load_session("sess1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"
    assert msgs[1]["role"] == "assistant"

@pytest.mark.asyncio
async def test_load_empty_session(history):
    msgs = history.load_session("nonexistent")
    assert msgs == []

@pytest.mark.asyncio
async def test_list_sessions(history):
    history.save_message("a", "user", "msg1")
    history.save_message("b", "user", "msg2")
    sessions = history.list_sessions()
    assert "a" in sessions
    assert "b" in sessions

@pytest.mark.asyncio
async def test_delete_session(history):
    history.save_message("delme", "user", "data")
    assert "delme" in history.list_sessions()
    history.delete_session("delme")
    assert "delme" not in history.list_sessions()

@pytest.mark.asyncio
async def test_prune_old_sessions(history):
    for i in range(5):
        history.save_message(f"s{i}", "user", f"msg{i}")
    sessions = history.list_sessions()
    assert len(sessions) <= 3


@pytest.mark.asyncio
async def test_load_messages_ordered(history):
    history.save_message("ordered", "user", "first")
    history.save_message("ordered", "assistant", "second")
    history.save_message("ordered", "user", "third")
    msgs = history.load_session("ordered")
    assert len(msgs) == 3
    assert msgs[0]["content"] == "first"
    assert msgs[1]["content"] == "second"
    assert msgs[2]["content"] == "third"


@pytest.mark.asyncio
async def test_async_save_and_load(history):
    await history.async_save_message("async_sess", "user", "async hello")
    await history.async_save_message("async_sess", "assistant", "async world")
    msgs = await history.async_load_session("async_sess")
    assert len(msgs) == 2


@pytest.mark.asyncio
async def test_async_load_empty(history):
    msgs = await history.async_load_session("no_such_session")
    assert msgs == []


def test_save_message_with_no_content(history):
    history.save_message("empty", "user", "")
    msgs = history.load_session("empty")
    assert len(msgs) == 1


def test_multiple_sessions_independent(history):
    history.save_message("sess_a", "user", "aaa")
    history.save_message("sess_a", "user", "bbb")
    history.save_message("sess_b", "user", "ccc")
    assert len(history.load_session("sess_a")) == 2
    assert len(history.load_session("sess_b")) == 1


def test_max_sessions_enforced(history):
    for i in range(5):
        history.save_message(f"session_{i}", "user", f"data_{i}")
    sessions = history.list_sessions()
    assert len(sessions) <= 3


def test_connection_initialized_eagerly(tmp_path):
    db_path = str(tmp_path / "eager.db")
    h = ChatHistoryManager(db_path)
    conn = h._get_conn()
    assert conn is not None
    h.close()


@pytest.mark.asyncio
async def test_async_methods_fall_back_to_sync(history):
    await history.async_save_message("sync", "user", "content")
    msgs = history.load_session("sync")
    assert len(msgs) == 1


def test_delete_nonexistent_session(history):
    history.delete_session("ghost")
    assert "ghost" not in history.list_sessions()

def test_search_messages(history):
    history.save_message("search_sess", "user", "find this keyword")
    history.save_message("search_sess", "assistant", "response with keyword")
    results = history.search_messages("search_sess", "keyword")
    assert len(results) == 2

def test_search_messages_no_match(history):
    history.save_message("s", "user", "content")
    results = history.search_messages("s", "nonexistent")
    assert results == []

def test_rename_session(history):
    history.save_message("old", "user", "data")
    assert history.rename_session("old", "new") is True
    assert "old" not in history.list_sessions()
    assert "new" in history.list_sessions()

def test_rename_nonexistent(history):
    assert history.rename_session("ghost", "new") is False

def test_fork_session(history):
    history.save_message("src", "user", "hello")
    history.save_message("src", "assistant", "world")
    count = history.fork_session("src", "dst")
    assert count == 2
    assert len(history.load_session("dst")) == 2

def test_undo_last_messages(history):
    history.save_message("undo_sess", "user", "msg1")
    history.save_message("undo_sess", "assistant", "msg2")
    history.save_message("undo_sess", "user", "msg3")
    removed = history.undo_last_messages("undo_sess", 2)
    assert removed == 2
    assert len(history.load_session("undo_sess")) == 1

def test_list_sessions_empty(history):
    sessions = history.list_sessions()
    assert sessions == []
