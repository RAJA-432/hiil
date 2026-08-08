"""Tests for ``eval.token_bench`` (hermetic RAG context-budget benchmark)."""

from __future__ import annotations

import math

from eval.token_bench import LARGE, SMALL, main, run_benchmark

CONFIG_NAMES = {"206-budget", "4k-budget"}


def _assert_valid_metrics(metrics: dict) -> None:
    assert isinstance(metrics["documents"], int)
    assert isinstance(metrics["chunks_total"], int)
    assert isinstance(metrics["chunks_fit"], int)
    assert isinstance(metrics["context_tokens_used"], int)
    assert isinstance(metrics["budget"], int)
    assert isinstance(metrics["coverage_pct"], float)
    assert isinstance(metrics["overhead_pct"], float)
    assert isinstance(metrics["score"], float)
    assert 0.0 <= metrics["coverage_pct"] <= 1.0
    assert 0.0 <= metrics["overhead_pct"] <= 1.0
    assert math.isfinite(metrics["score"])


def test_run_benchmark_returns_both_configs_with_valid_metrics():
    report = run_benchmark(n_docs=4, seed=1)
    assert set(report["configs"]) == CONFIG_NAMES
    for metrics in report["configs"].values():
        _assert_valid_metrics(metrics)
    assert report["winner"] in CONFIG_NAMES
    assert isinstance(report["recommendation"], str)
    assert report["recommendation"]


def test_large_budget_fits_more_chunks():
    report = run_benchmark(n_docs=4, seed=1)
    small = report["configs"]["206-budget"]
    large = report["configs"]["4k-budget"]
    assert large["coverage_pct"] >= small["coverage_pct"]
    assert large["chunks_fit"] >= small["chunks_fit"]


def test_cli_main_returns_zero_and_prints_table(capsys):
    rc = main(["--docs", "4", "--seed", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    for header in ("config", "budget", "coverage", "score", "winner", "recommendation"):
        assert header in out


def test_module_import_is_hermetic():
    import eval.token_bench as module

    assert callable(module.run_benchmark)
    assert SMALL["name"] == "206-budget"
    assert LARGE["name"] == "4k-budget"
