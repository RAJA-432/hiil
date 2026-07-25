import pytest

from mcp_cli.services.usage import (
    UsageTracker,
    _detect_family,
    _encoding_for_model,
    count_tokens,
    estimate_cost,
)


def test_detect_family_gpt4():
    assert _detect_family("gpt-4-turbo") == "gpt-4-turbo"


def test_detect_family_gpt4o():
    assert _detect_family("gpt-4o-2024-08-06") == "gpt-4o"


def test_detect_family_claude():
    assert _detect_family("claude-3-opus-20240229") == "claude-3-opus-20240229"


def test_detect_family_unknown():
    assert _detect_family("unknown-model") == "gpt-4o"


def test_detect_family_deepseek():
    assert _detect_family("deepseek-chat") == "deepseek-chat"


def test_encoding_for_model():
    assert _encoding_for_model("gpt-4") == "cl100k_base"
    assert _encoding_for_model("gpt-3.5-turbo") == "cl100k_base"
    assert _encoding_for_model("text-embedding-ada-002") == "cl100k_base"
    assert _encoding_for_model("davinci") == "p50k_base"
    assert _encoding_for_model("unknown") == "cl100k_base"


def test_count_tokens():
    tokens = count_tokens("Hello, world!", "gpt-4")
    assert tokens > 0


def test_count_tokens_empty():
    tokens = count_tokens("", "gpt-4")
    assert tokens >= 0


def test_estimate_cost_gpt4():
    cost = estimate_cost("gpt-4", 1000, 500)
    assert cost == pytest.approx(0.06, rel=0.01)


def test_estimate_cost_gpt4o():
    cost = estimate_cost("gpt-4o", 1000, 500)
    assert cost == pytest.approx(0.0075, rel=0.01)


def test_estimate_cost_unknown():
    cost = estimate_cost("fake-model", 1000, 500)
    assert cost == pytest.approx(0.0075, rel=0.01)


@pytest.fixture
def tracker(tmp_path):
    db = str(tmp_path / "usage.db")
    u = UsageTracker(db)
    yield u
    u.close()


def test_record_and_summary(tracker):
    tracker.record("gpt-4", 1000, 500, "sess1")
    s = tracker.session_summary()
    assert s["input_tokens"] == 1000
    assert s["output_tokens"] == 500
    assert s["total_tokens"] == 1500
    assert s["cost"] > 0


def test_total_summary(tracker):
    tracker.record("gpt-4", 1000, 500, "s1")
    tracker.record("gpt-4", 200, 100, "s2")
    t = tracker.total_summary()
    assert t["input_tokens"] == 1200
    assert t["output_tokens"] == 600


def test_history(tracker):
    tracker.record("gpt-4", 100, 50, "s1")
    h = tracker.history(limit=10)
    assert len(h) == 1
    assert h[0]["model"] == "gpt-4"
    assert h[0]["session_id"] == "s1"


def test_session_reset_on_new_tracker(tracker):
    tracker.record("gpt-4o", 500, 200)
    s1 = tracker.session_summary()
    tracker2 = UsageTracker(tracker.db_path)
    s2 = tracker2.session_summary()
    assert s2["total_tokens"] == 0
    tracker2.close()


def test_record_zero_tokens(tracker):
    tracker.record("gpt-4", 0, 0, "zero_sess")
    s = tracker.session_summary()
    assert s["input_tokens"] == 0
    assert s["output_tokens"] == 0
    assert s["total_tokens"] == 0
    assert s["cost"] == 0


def test_record_multiple_models(tracker):
    tracker.record("gpt-4", 1000, 500, "multi")
    tracker.record("gpt-4o", 2000, 1000, "multi")
    s = tracker.session_summary()
    assert s["input_tokens"] == 3000
    assert s["output_tokens"] == 1500


def test_history_ordered_by_id(tracker):
    tracker.record("gpt-4", 10, 5, "s1")
    tracker.record("gpt-4", 20, 10, "s2")
    h = tracker.history(limit=10)
    assert len(h) == 2


def test_history_limit(tracker):
    for i in range(20):
        tracker.record("gpt-4", 1, 1, f"s{i}")
    h = tracker.history(limit=5)
    assert len(h) == 5


def test_detect_family_gemma():
    assert _detect_family("gemma4:31b-cloud") == "gpt-4o"


def test_estimate_cost_claude3():
    cost = estimate_cost("claude-3-opus-20240229", 1000, 500)
    assert cost > 0


def test_estimate_cost_deepseek():
    cost = estimate_cost("deepseek-chat", 1000, 500)
    assert cost == pytest.approx(0.00027, rel=0.1)


def test_count_tokens_unicode():
    tokens = count_tokens("🔥 🚀 测试 ключ", "gpt-4")
    assert tokens > 0


def test_count_tokens_long_string():
    tokens = count_tokens("hello " * 1000, "gpt-4")
    assert tokens > 100


def test_detect_family_empty_string():
    assert _detect_family("") == "gpt-4o"


def test_close_idempotent(tracker):
    tracker.close()
    tracker.close()


@ pytest.mark.asyncio
async def test_async_history(tracker):
    tracker.record("gpt-4", 100, 50, "s1")
    h = await tracker.async_history(limit=10)
    assert len(h) == 1
    assert h[0]["model"] == "gpt-4"


def test_connection_initialized_eagerly(tmp_path):
    db = str(tmp_path / "eager_usage.db")
    t = UsageTracker(db)
    conn = t._get_conn()
    assert conn is not None
    t.close()


@pytest.mark.asyncio
async def test_async_record(tracker):
    await tracker.async_record("gpt-4", 500, 300, "async_sess")
    s = tracker.session_summary()
    assert s["input_tokens"] == 500
    assert s["output_tokens"] == 300


@pytest.mark.asyncio
async def test_async_total_summary(tracker):
    await tracker.async_record("gpt-4", 100, 50, "s1")
    await tracker.async_record("gpt-4", 200, 100, "s2")
    t = await tracker.async_total_summary()
    assert t["input_tokens"] == 300


def test_count_tokens_mixed_content():
    code = "def hello():\n    print('world')\n"
    tokens = count_tokens(code, "gpt-4")
    assert tokens > 0
