from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cli.services.context_manager import ContextManager


@pytest.fixture
def cm():
    claude = MagicMock()
    claude.model = "gpt-4o"
    vs = MagicMock()
    return ContextManager(claude, vs, max_context_tokens=100)


def test_under_budget_returns_original(cm):
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    result = cm.trim(msgs)
    assert result is msgs


def test_over_budget_trims_to_recent(cm):
    cm.max_context_tokens = 5
    msgs = [{"role": "user", "content": "a" * 100}] * 10
    result = cm.trim(msgs)
    assert len(result) < len(msgs)
    assert any("[compacted" in m.get("content", "") for m in result if m["role"] == "system")


def test_empty_messages(cm):
    result = cm.trim([])
    assert result == []


def test_single_message(cm):
    result = cm.trim([{"role": "user", "content": "hello"}])
    assert len(result) == 1
    assert result[0]["content"] == "hello"


def test_increments_compact_count(cm):
    cm.max_context_tokens = 1
    msgs = [{"role": "user", "content": "x" * 100}] * 5
    cm.trim(msgs)
    assert cm.compact_count == 1
    cm.trim(msgs)
    assert cm.compact_count == 2


def test_preserves_system_message_when_under_budget(cm):
    msgs = [
        {"role": "system", "content": "you are helpful"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = cm.trim(msgs)
    assert len(result) == 3


def test_content_truncation_when_very_over_budget(cm):
    cm.max_context_tokens = 10
    long = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt " * 20
    msgs = [{"role": "user", "content": long}]
    result = cm.trim(msgs)
    assert len(result) >= 1
    sys_msgs = [m for m in result if m["role"] == "system"]
    assert len(sys_msgs) == 1


def test_preserves_tool_call_messages(cm):
    cm.max_context_tokens = 10
    msgs = [
        {"role": "user", "content": "do something"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "function": {"name": "t", "arguments": "{}"}, "type": "function"}]},
        {"role": "tool", "content": "result"},
    ]
    result = cm.trim(msgs)
    assert len(result) >= 1


def test_non_standard_roles(cm):
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "function", "content": "func result"},
        {"role": "assistant", "content": "ok"},
    ]
    result = cm.trim(msgs)
    assert len(result) >= 1


def test_result_starts_with_system_summary_when_trimmed(cm):
    cm.max_context_tokens = 5
    msgs = [{"role": "user", "content": "x" * 80}] * 8
    result = cm.trim(msgs)
    assert result[0]["role"] == "system"
    assert "compacted" in result[0]["content"]
    assert "kept" in result[0]["content"]


def test_messages_with_empty_content(cm):
    msgs = [{"role": "user", "content": ""}, {"role": "assistant", "content": ""}]
    result = cm.trim(msgs)
    assert len(result) == 2


def test_message_tokens(cm):
    t = cm.message_tokens([{"role": "user", "content": "hello world"}])
    assert t > 0
    assert isinstance(t, int)


def test_auto_index_skips_short_text(cm):
    cm.vector_store.async_list_keys = AsyncMock(return_value=[])
    cm.claude.embed = AsyncMock(return_value=[0.5, 0.5])
    import asyncio
    asyncio.run(cm.auto_index("short", "messages"))
    cm.vector_store.async_index.assert_not_called()


def test_auto_index_indexes_long_text(cm):
    cm.vector_store.async_list_keys = AsyncMock(return_value=["msg_0", "msg_1"])
    cm.vector_store.async_index = AsyncMock()
    cm.claude.embed = AsyncMock(return_value=[0.5, 0.5])
    import asyncio
    asyncio.run(cm.auto_index("this is a sufficiently long message to index", "messages"))
    cm.vector_store.async_index.assert_called_once()
    args = cm.vector_store.async_index.call_args
    assert args[0][0] == "messages"
    assert args[0][1] == "msg_2"


def test_auto_index_skips_when_no_embedding(cm):
    cm.vector_store.async_list_keys = AsyncMock(return_value=[])
    cm.claude.embed = AsyncMock(return_value=[])
    import asyncio
    asyncio.run(cm.auto_index("this is a sufficiently long message to index", "messages"))
    cm.vector_store.async_index.assert_not_called()


def test_semantic_search_returns_results(cm):
    cm.claude.embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    cm.vector_store.async_search = AsyncMock(return_value=[{"key": "test1", "text": "hello world", "score": 1.0}])
    import asyncio
    results = asyncio.run(cm.semantic_search("hello"))
    assert len(results) == 1
    assert results[0]["key"] == "test1"


def test_fetch_model_context_no_base_url(cm):
    cm.claude.base_url = None
    import asyncio
    result = asyncio.run(cm.fetch_model_context("gpt-4o"))
    assert result is None


def test_fetch_model_context_api_error(cm):
    cm.claude.base_url = "http://localhost:11434/v1"
    cm.claude.api_key = ""
    with patch("httpx.AsyncClient") as mock_httpx:
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.get = AsyncMock(side_effect=RuntimeError("timeout"))
        mock_httpx.return_value = mock_instance
        import asyncio
        result = asyncio.run(cm.fetch_model_context("gemma4"))
        assert result is None
