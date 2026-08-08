"""Hermetic model-selection A/B benchmark for context-window scaling.

Compares candidate model profiles for the RAG chat stack against simulated
request token distributions, without loading any model or calling a network:

* ``current``          — 4K window (the phase-2 target ceiling)
* ``longformer-base``  — 4K, sparse attention, cheaper
* ``longformer-large`` — 4K, larger, better quality
* ``rwkv-4-world``     — 32K, linear attention, cheap
* ``llama-3.1-8b``     — 128K, frontier-class window

Metrics per model: fit rate (requests whose input fits within the window minus
an output reserve), average cost, throughput score, and a value = fit * quality
/ cost. A pure-math simulation so it runs safely in CI.

Usage: ``python -m eval.model_ab [--questions 50] [--seed 42] [--avg-input 1800]``
"""

from __future__ import annotations

import argparse
import random
import sys

try:
    from mcp_cli.services.prompt_budget import TokenAwareSampler as _Sampler
except ImportError:  # pragma: no cover - module added in parallel
    _Sampler = None

PROFILES = [
    {"id": "current", "context_window": 4096, "max_output": 1024,
     "rel_cost": 1.0, "rel_quality": 0.80},
    {"id": "longformer-base", "context_window": 4096, "max_output": 512,
     "rel_cost": 0.6, "rel_quality": 0.70},
    {"id": "longformer-large", "context_window": 4096, "max_output": 512,
     "rel_cost": 0.9, "rel_quality": 0.82},
    {"id": "rwkv-4-world", "context_window": 32768, "max_output": 2048,
     "rel_cost": 0.5, "rel_quality": 0.75},
    {"id": "llama-3.1-8b", "context_window": 131072, "max_output": 4096,
     "rel_cost": 0.8, "rel_quality": 0.85},
]


def _input_samples(n_questions: int, seed: int, avg_input: int) -> list[int]:
    """Deterministic list of per-request input token counts."""
    rng = random.Random(seed)
    return [max(1, int(rng.gauss(avg_input, avg_input * 0.25))) for _ in range(n_questions)]


def run_ab(
    n_questions: int = 50,
    seed: int = 42,
    avg_input_tokens: int = 1800,
) -> dict:
    samples = _input_samples(n_questions, seed, avg_input_tokens)
    models: dict[str, dict] = {}
    for profile in PROFILES:
        window = int(profile["context_window"])
        reserve = 512
        budget = max(1, window - reserve)
        fit = sum(1 for t in samples if t <= budget)
        fit_pct = fit / len(samples) if samples else 0.0
        avg_cost = float(profile["rel_cost"]) * (avg_input_tokens / 1000)
        throughput = 1000.0 / window
        quality = float(profile["rel_quality"])
        value = (fit_pct * quality) / avg_cost if avg_cost else 0.0
        models[profile["id"]] = {
            "context_window": window,
            "max_output": profile["max_output"],
            "fit_pct": round(fit_pct, 4),
            "avg_cost": round(avg_cost, 4),
            "throughput": round(throughput, 6),
            "value": round(value, 6),
        }
    winner = max(models, key=lambda name: models[name]["value"])

    sampler_pick: str | None = None
    if _Sampler is not None:
        try:
            sampler = _Sampler(max_total=max(samples), reserve_output=512)
            candidates = [
                {"id": p["id"], "context_window": p["context_window"],
                 "max_output": p["max_output"]} for p in PROFILES
            ]
            picked = sampler.select_model(max(samples), candidates)
            sampler_pick = picked["id"] if picked else None
        except Exception:
            sampler_pick = None

    recommendation = recommend_phase(avg_input_tokens, window=winner)
    return {
        "models": models,
        "winner": winner,
        "sampler_pick": sampler_pick,
        "recommendation": recommendation,
    }


def recommend_phase(current_avg: int = 206, target: int = 4096, window: str | None = None) -> str:
    """Explain the tiered scaling recommendation 206 → 4K → 32K → 128K."""
    best = f"the {window}-window model" if window else "a larger-window model"
    return (
        f"Average input ~{current_avg} tokens, target ceiling {target}. "
        "Scale in tiers: 206 -> 4K (practical baseline), 4K -> 32K (competitive), "
        "32K -> 128K+ (frontier). Today " + best + " fits the phase-2 target; adopt an "
        "RWVK-style linear-attention or a 128K llama-class window only when "
        "multi-document retrieval starts pushing past the 4K budget."
    )


def print_table(report: dict) -> str:
    """Print and return a human-readable model comparison table."""
    header = (
        f"{'model':<16} {'window':<8} {'max_out':<8} {'fit%':<7} "
        f"{'avg_cost':<9} {'throughput':<11} {'value':<8}"
    )
    lines = [header, "-" * len(header)]
    for name, metrics in report["models"].items():
        lines.append(
            f"{name:<16} {metrics['context_window']:<8} {metrics['max_output']:<8} "
            f"{metrics['fit_pct']:<7} {metrics['avg_cost']:<9} "
            f"{metrics['throughput']:<11} {metrics['value']:<8}"
        )
    table = "\n".join(lines)
    print(table)
    return table


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: print the table and recommendation, exit 0."""
    parser = argparse.ArgumentParser(prog="eval.model_ab")
    parser.add_argument("--questions", type=int, default=50, help="Number of simulated requests (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--avg-input", type=int, default=1800, help="Mean input tokens per request (default: 1800)")
    args = parser.parse_args(argv)
    report = run_ab(n_questions=args.questions, seed=args.seed, avg_input_tokens=args.avg_input)
    print_table(report)
    print(f"winner: {report['winner']}")
    if report["sampler_pick"]:
        print(f"sampler pick: {report['sampler_pick']}")
    print(f"recommendation: {report['recommendation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
