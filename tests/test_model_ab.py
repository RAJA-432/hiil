from __future__ import annotations

from eval.model_ab import PROFILES, recommend_phase, run_ab


class TestModelAB:
    def test_run_ab_returns_all_models(self) -> None:
        report = run_ab(n_questions=10, seed=1)
        assert set(report["models"].keys()) == {p["id"] for p in PROFILES}
        assert report["winner"] in report["models"]
        for metrics in report["models"].values():
            assert 0.0 <= metrics["fit_pct"] <= 1.0
            assert metrics["avg_cost"] >= 0.0
            assert metrics["value"] >= 0.0

    def test_larger_windows_have_higher_fit(self) -> None:
        report = run_ab(n_questions=100, seed=3, avg_input_tokens=20000)
        models = report["models"]
        assert models["llama-3.1-8b"]["fit_pct"] >= models["rwkv-4-world"]["fit_pct"]
        assert models["rwkv-4-world"]["fit_pct"] >= models["current"]["fit_pct"]

    def test_deterministic_for_same_seed(self) -> None:
        assert run_ab(n_questions=20, seed=9) == run_ab(n_questions=20, seed=9)

    def test_recommend_phase_lists_tiers(self) -> None:
        text = recommend_phase(206, 4096)
        assert "206" in text and "4K" in text and "32K" in text and "128K" in text

    def test_cli_returns_zero(self, capsys) -> None:
        from eval.model_ab import main

        assert main(["--questions", "10", "--seed", "1"]) == 0
        out = capsys.readouterr().out
        assert "winner:" in out
        assert "recommendation:" in out
