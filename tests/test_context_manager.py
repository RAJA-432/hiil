from __future__ import annotations

from unittest.mock import patch

import mcp_cli.services.context_manager as cm_module
from mcp_cli.services.context_manager import ContextManager
from mcp_cli.services.usage import count_tokens


class FakeClaude:
    model = "test-model"


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def _build_history(n: int, words_per_msg: int = 30) -> list[dict]:
    filler = " ".join(["lorem", "ipsum", "dolor", "sit", "amet", "consectetur"] * words_per_msg)
    return [_msg("user" if i % 2 == 0 else "assistant", f"msg{i}: {filler}") for i in range(n)]


def _total_tokens(messages: list[dict]) -> int:
    return sum(count_tokens(m.get("content", ""), FakeClaude.model) for m in messages)


def test_trim_under_budget_returns_same_object():
    messages = _build_history(5)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=100_000)
    assert cm.trim(messages) is messages


def test_trim_over_budget_returns_within_budget():
    messages = _build_history(200)
    budget = 3000
    cm = ContextManager(FakeClaude(), None, max_context_tokens=budget)
    result = cm.trim(messages)
    assert len(result) >= 2
    assert result[0]["role"] == "system"
    assert "[compacted" in result[0]["content"]
    assert _total_tokens(result) <= budget
    kept = result[1:]
    original_slice = messages[-len(kept):]
    assert all(kept[i] is original_slice[i] for i in range(len(kept)))


def test_trim_keeps_oldest_survivor_first():
    messages = _build_history(50)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=2000)
    result = cm.trim(messages)
    kept = result[1:]
    assert kept[0] is messages[-len(kept):][0]
    assert kept[-1] is messages[-1]


def test_trim_reserves_tools_tokens():
    messages = _build_history(150)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=3000)
    without_tools = cm.trim(messages)
    with_tools = cm.trim(messages, tools_token_count=1500)
    assert len(without_tools) >= 2
    assert len(with_tools) >= 2
    assert len(with_tools) < len(without_tools)
    assert _total_tokens(with_tools) <= 1500


def test_trim_empty_history():
    cm = ContextManager(FakeClaude(), None, max_context_tokens=1000)
    assert cm.trim([]) == []


def test_trim_single_message_over_budget_stays_nonempty():
    messages = [_msg("user", "word " * 400)]
    cm = ContextManager(FakeClaude(), None, max_context_tokens=50)
    result = cm.trim(messages)
    assert len(result) >= 2
    assert result[0]["role"] == "system"


def test_trim_two_large_messages_stays_small():
    messages = [
        _msg("user", "word " * 500),
        _msg("assistant", "word " * 500),
    ]
    cm = ContextManager(FakeClaude(), None, max_context_tokens=100)
    result = cm.trim(messages)
    assert len(result) >= 2
    assert result[0]["role"] == "system"


def test_trim_non_positive_budget_keeps_last_two():
    messages = _build_history(5)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=10)
    result = cm.trim(messages, tools_token_count=20)
    assert result == messages[-2:]


def test_trim_counts_each_message_at_most_once():
    messages = _build_history(300)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=4000)
    real = cm_module.count_tokens
    calls = {"n": 0}

    def counting(text, model="gpt-4o"):
        calls["n"] += 1
        return real(text, model)

    with patch("mcp_cli.services.context_manager.count_tokens", new=counting):
        cm.trim(messages)

    assert len(messages) <= calls["n"]
    assert calls["n"] <= int(len(messages) * 1.5)


def test_count_tokens_caches_repeated_text():
    from mcp_cli.services import usage

    key_text = "cache probe text alpha beta gamma delta"
    helper = usage._count_text_tokens
    before = helper.cache_info()
    first = count_tokens(key_text, "gpt-4o")
    second = count_tokens(key_text, "gpt-4o")
    assert first == second
    after = helper.cache_info()
    assert after.hits - before.hits >= 1
    assert after.misses - before.misses >= 1


def test_count_tokens_cache_distinct_per_model():
    from mcp_cli.services import usage

    key_text = "model sensitive probe text"
    helper = usage._count_text_tokens
    before = helper.cache_info()
    first = count_tokens(key_text, "gpt-4o")
    second = count_tokens(key_text, "gpt-3.5-turbo")
    assert first == second
    after = helper.cache_info()
    assert after.misses - before.misses >= 2


def test_count_tokens_dict_key_order_independent():
    a = count_tokens({"role": "user", "content": "hello world"}, "gpt-4o")
    b = count_tokens({"content": "hello world", "role": "user"}, "gpt-4o")
    assert a == b


class NoCacheCM(ContextManager):
    def _token_count(self, content):
        return count_tokens(content, self.claude.model)


def test_trim_token_cache_reused_across_calls():
    messages = _build_history(300)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=4000)
    calls = {"n": 0}

    def counting(text, model="gpt-4o"):
        calls["n"] += 1
        return len(text) // 4

    with patch("mcp_cli.services.context_manager.count_tokens", new=counting):
        first = cm.trim([dict(m) for m in messages])
        first_calls = calls["n"]
        second = cm.trim([dict(m) for m in messages])
        second_calls = calls["n"] - first_calls

    assert first_calls > 100
    assert second_calls <= 10


def test_trim_output_identical_before_after_cache():
    messages = _build_history(120)
    cm = ContextManager(FakeClaude(), None, max_context_tokens=2500)
    reference = NoCacheCM(FakeClaude(), None, max_context_tokens=2500)
    real = cm_module.count_tokens

    with patch("mcp_cli.services.context_manager.count_tokens", new=real):
        cached_result = cm.trim([dict(m) for m in messages])
        uncached_result = reference.trim([dict(m) for m in messages])

    assert cached_result == uncached_result


def test_token_cache_bounded_and_correct():
    cm = ContextManager(FakeClaude(), None, max_context_tokens=10_000_000)

    def counting(text, model="gpt-4o"):
        return max(1, len(text) // 4)

    with patch("mcp_cli.services.context_manager.count_tokens", new=counting):
        for i in range(cm._max_cache_entries + 100):
            cm._token_count(f"cache-cap-content-{i}")
        assert len(cm._token_cache) <= cm._max_cache_entries
        assert cm._token_count("cache-cap-content-0") == counting("cache-cap-content-0")
