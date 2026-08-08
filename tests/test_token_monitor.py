from __future__ import annotations

from mcp_cli.services.token_monitor import (
    HARD_THRESHOLD,
    WARN_THRESHOLD,
    TokenMonitor,
    TokenSample,
    classify,
    format_status,
)


def test_classify_boundaries():
    assert classify(3499, WARN_THRESHOLD, HARD_THRESHOLD) == "ok"
    assert classify(WARN_THRESHOLD, WARN_THRESHOLD, HARD_THRESHOLD) == "warn"
    assert classify(3799, WARN_THRESHOLD, HARD_THRESHOLD) == "warn"
    assert classify(HARD_THRESHOLD, WARN_THRESHOLD, HARD_THRESHOLD) == "critical"
    assert classify(4000, WARN_THRESHOLD, HARD_THRESHOLD) == "critical"


def test_classify_with_custom_thresholds():
    assert classify(99, 100, 200) == "ok"
    assert classify(100, 100, 200) == "warn"
    assert classify(200, 100, 200) == "critical"


def test_token_sample_from_record_computes_total_and_level():
    sample = TokenSample.from_record(1000, 1500, 1000, "s1")
    assert sample.total_tokens == 3500
    assert sample.level == "warn"
    assert sample.session_id == "s1"

    ok_sample = TokenSample.from_record(100, 100, 0, "s1")
    assert ok_sample.total_tokens == 200
    assert ok_sample.level == "ok"
    assert ok_sample.input_tokens == 100
    assert ok_sample.output_tokens == 100
    assert ok_sample.context_tokens == 0


def test_token_sample_level_for_helper():
    assert TokenSample.level_for(2000, 3500, 3800) == "ok"
    assert TokenSample.level_for(3600, 3500, 3800) == "warn"
    assert TokenSample.level_for(3900, 3500, 3800) == "critical"


def test_record_level_boundaries():
    monitor = TokenMonitor()
    ok = monitor.record(2000, 1499)
    assert ok["level"] == "ok"
    assert ok["total_tokens"] == 3499

    warn = monitor.record(3500, 0)
    assert warn["level"] == "warn"
    assert warn["total_tokens"] == 3500

    critical = monitor.record(3800, 0)
    assert critical["level"] == "critical"
    assert critical["warn_threshold"] == WARN_THRESHOLD
    assert critical["hard_threshold"] == HARD_THRESHOLD
    assert critical["context_tokens"] == 0


def test_record_with_custom_thresholds():
    monitor = TokenMonitor(warn_threshold=100, hard_threshold=200)
    status = monitor.record(150, 0)
    assert status["level"] == "warn"
    assert status["warn_threshold"] == 100
    assert status["hard_threshold"] == 200


def test_record_bounds_deque_to_max_recent():
    monitor = TokenMonitor(max_recent=3)
    for i in range(1, 6):
        monitor.record(i * 100, i * 50)
    assert monitor.sample_count() == 3
    status = monitor.status()
    assert status["recent_count"] == 3
    assert status["avg_input"] == 400
    assert status["max_total"] == 750


def test_status_aggregates_averages_and_max():
    monitor = TokenMonitor()
    monitor.record(100, 50)
    monitor.record(200, 100)
    monitor.record(300, 150)
    status = monitor.status()
    assert status["recent_count"] == 3
    assert status["avg_input"] == 200
    assert status["avg_output"] == 100
    assert status["max_total"] == 450
    assert status["warnings"] == 0
    assert status["critical_hits"] == 0
    assert status["level"] == "ok"
    assert status["last"]["total_tokens"] == 450


def test_status_filters_by_session():
    monitor = TokenMonitor()
    monitor.record(100, 50, session_id="a")
    monitor.record(200, 100, session_id="a")
    monitor.record(300, 150, session_id="b")
    all_status = monitor.status()
    assert all_status["recent_count"] == 3
    assert all_status["avg_input"] == 200
    assert all_status["max_total"] == 450
    b_status = monitor.status("b")
    assert b_status["recent_count"] == 1
    assert b_status["avg_input"] == 300
    assert b_status["avg_output"] == 150
    assert b_status["max_total"] == 450
    assert b_status["last"]["session_id"] == "b"
    a_status = monitor.status("a")
    assert a_status["recent_count"] == 2
    assert a_status["max_total"] == 300


def test_status_counts_warnings_and_critical_hits():
    monitor = TokenMonitor()
    monitor.record(1000, 1000)
    monitor.record(3500, 0)
    monitor.record(3800, 0)
    status = monitor.status()
    assert status["warnings"] == 1
    assert status["critical_hits"] == 1
    assert status["level"] == "critical"


def test_status_empty_monitor():
    monitor = TokenMonitor()
    status = monitor.status()
    assert status["recent_count"] == 0
    assert status["last"] is None
    assert status["avg_input"] == 0
    assert status["avg_output"] == 0
    assert status["max_total"] == 0
    assert status["level"] == "ok"
    assert status["warnings"] == 0
    assert status["critical_hits"] == 0


def test_should_fallback_toggles_on_latest_level():
    monitor = TokenMonitor()
    assert monitor.should_fallback() is False
    monitor.record(3500, 0)
    assert monitor.should_fallback() is True
    monitor.record(100, 100)
    assert monitor.should_fallback() is False


def test_should_fallback_on_recent_average():
    monitor = TokenMonitor()
    monitor.record(3520, 0)
    monitor.record(3495, 0)
    monitor.record(3495, 0)
    assert monitor.should_fallback() is True


def test_should_fallback_false_when_well_below_thresholds():
    monitor = TokenMonitor()
    for _ in range(5):
        monitor.record(100, 100)
    assert monitor.should_fallback() is False


def test_fallback_action():
    monitor = TokenMonitor()
    assert monitor.fallback_action() == "none"
    monitor.record(3500, 0)
    assert monitor.fallback_action() == "compress"
    monitor.record(3800, 0)
    assert monitor.fallback_action() == "truncate"
    monitor.record(100, 100)
    assert monitor.fallback_action() == "none"


def test_format_status_record_dict():
    status = {"total_tokens": 3421, "input_tokens": 2100, "output_tokens": 1321, "level": "warn"}
    assert format_status(status) == "tokens: 3421 (in 2100 / out 1321) [warn]"


def test_format_status_handles_aggregate_status():
    monitor = TokenMonitor()
    monitor.record(100, 50)
    line = format_status(monitor.status())
    assert "tokens: 150" in line
    assert "in 100" in line
    assert "out 50" in line
    assert "[ok]" in line


def test_reset_clears_all():
    monitor = TokenMonitor()
    monitor.record(100, 100)
    monitor.record(200, 200)
    assert monitor.sample_count() == 2
    monitor.reset()
    assert monitor.sample_count() == 0
    assert monitor.status()["recent_count"] == 0
    assert monitor.status()["last"] is None
    assert monitor.fallback_action() == "none"


def test_reset_scoped_to_session():
    monitor = TokenMonitor()
    monitor.record(100, 100, session_id="a")
    monitor.record(100, 100, session_id="b")
    monitor.record(200, 200, session_id="b")
    monitor.reset("b")
    assert monitor.sample_count() == 1
    assert monitor.status()["recent_count"] == 1
    assert monitor.status()["last"]["session_id"] == "a"


def test_hermetic_import_and_use():
    monitor = TokenMonitor()
    result = monitor.record(100, 200)
    assert result["level"] == "ok"
    assert monitor.status()["recent_count"] == 1
    assert monitor.sample_count() == 1
    assert format_status(result) == "tokens: 300 (in 100 / out 200) [ok]"
