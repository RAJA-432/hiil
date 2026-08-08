from __future__ import annotations

from eval.embedding_bench import (
    generate_corpus,
    run_benchmark,
    score_candidates,
)


class TestEmbeddingBench:
    def test_corpus_is_deterministic(self) -> None:
        a = generate_corpus(10, seed=7)
        b = generate_corpus(10, seed=7)
        assert a == b
        assert len(a) == 10

    def test_score_candidates_returns_all_profiles(self) -> None:
        corpus = generate_corpus(20, seed=1)
        rows = score_candidates(
            [{"name": "x", "dim": 1, "rel_quality": 0.8, "rel_cost": 1.0}],
            corpus,
            query_topic="alpha",
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "x"
        assert 0.0 <= row["recall_at_5"] <= 1.0
        assert row["value"] >= 0.0

    def test_run_benchmark_has_valid_winner(self) -> None:
        report = run_benchmark(n_docs=20, seed=1)
        assert report["winner"] in report["profiles"]
        assert report["recommendation"]
        for name, metrics in report["profiles"].items():
            assert 0.0 <= metrics["recall_at_5"] <= 1.0
            assert metrics["value"] >= 0.0

    def test_cli_returns_zero(self, capsys) -> None:
        from eval.embedding_bench import main

        assert main(["--docs", "10", "--seed", "1"]) == 0
        out = capsys.readouterr().out
        assert "winner:" in out
        assert "recommendation:" in out
