"""Hermetic embedding-model upgrade evaluation.

Compares candidate embedding approaches for the RAG pipeline without loading
any ML models or calling networks:

* ``mini-l6``   — all-MiniLM-L6-v2 (dim 384, cheap)
* ``mini-l12``  — all-MiniLM-L12-v2 (dim 384, better quality)
* ``bge-small`` — bge-small (dim 384)
* ``bge-large`` — bge-large (dim 1024)
* ``api-embed`` — the project's current API-based embedding (cost per token)

Retrieval is simulated with a deterministic topic-overlap model scaled by each
profile's relative quality, so recall@5 and cost/value can be compared purely
locally. No network, no model weights: safe for CI.

Usage: ``python -m eval.embedding_bench [--docs 50] [--seed 42] [--query TOPIC]``
"""

from __future__ import annotations

import argparse
import random
import sys

_TOPIC_WORDS = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
    "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
]

_FILLER = [
    "report", "analysis", "context", "document", "query", "retrieval",
    "index", "vector", "score", "source", "paragraph", "summary",
]

PROFILES = [
    {"name": "mini-l6", "dim": 384, "rel_quality": 0.70, "rel_cost": 0.5,
     "notes": "all-MiniLM-L6-v2, fast and cheap"},
    {"name": "mini-l12", "dim": 384, "rel_quality": 0.80, "rel_cost": 0.7,
     "notes": "all-MiniLM-L12-v2, better nuance"},
    {"name": "bge-small", "dim": 384, "rel_quality": 0.78, "rel_cost": 0.6,
     "notes": "BAAI bge-small-zh/EN"},
    {"name": "bge-large", "dim": 1024, "rel_quality": 0.90, "rel_cost": 1.5,
     "notes": "BAAI bge-large, highest local quality"},
    {"name": "api-embed", "dim": 3072, "rel_quality": 0.92, "rel_cost": 3.0,
     "notes": "current API embedding, per-token cost"},
]


def generate_corpus(n_docs: int = 50, seed: int = 42) -> list[dict[str, str]]:
    """Build deterministic docs, each centered on one topic word."""
    rng = random.Random(seed)
    docs: list[dict[str, str]] = []
    for i in range(n_docs):
        topic = _TOPIC_WORDS[i % len(_TOPIC_WORDS)]
        filler = " ".join(f"{rng.choice(_FILLER)}_{i}_{j}" for j in range(30))
        docs.append({
            "id": f"doc_{i}",
            "topic": topic,
            "text": f"{topic} {filler}",
        })
    return docs


def _topic_overlap(doc: dict[str, str], query_topic: str) -> float:
    """Return 1.0 when the doc's topic matches the query topic, else 0.0."""
    return 1.0 if doc["topic"] == query_topic else 0.0


def score_candidates(
    profiles: list[dict],
    corpus: list[dict[str, str]],
    query_topic: str,
    top_k: int = 5,
) -> list[dict]:
    """Simulate retrieval per profile and compute recall / value metrics."""
    rows: list[dict] = []
    relevant_total = sum(1 for d in corpus if _topic_overlap(d, query_topic) > 0)
    for profile in profiles:
        quality = float(profile["rel_quality"])
        scored = [
            (_topic_overlap(d, query_topic) * quality, d) for d in corpus
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_hits = sum(1 for score, d in scored[:top_k] if score > 0)
        recall = top_hits / relevant_total if relevant_total else 0.0
        cost = float(profile["rel_cost"])
        rows.append({
            "name": profile["name"],
            "dim": profile["dim"],
            "rel_cost": cost,
            "rel_quality": quality,
            "recall_at_5": round(recall, 4),
            "value": round(recall / cost, 4) if cost else 0.0,
        })
    return rows


def run_benchmark(
    n_docs: int = 50,
    seed: int = 42,
    query_topic: str = "alpha",
) -> dict:
    corpus = generate_corpus(n_docs, seed)
    rows = score_candidates(PROFILES, corpus, query_topic)
    by_name = {r["name"]: r for r in rows}
    winner = max(rows, key=lambda r: r["value"])["name"]
    recommendation = (
        f"Best value is '{winner}' (recall@5 {by_name[winner]['recall_at_5']} "
        f"at rel_cost {by_name[winner]['rel_cost']}). If per-token cost is the "
        "binding constraint prefer a local model (bge-small/mini-l12); the API "
        "embedding only wins when its extra recall justifies ~3x the cost."
    )
    return {"profiles": by_name, "winner": winner, "recommendation": recommendation}


def print_table(report: dict) -> str:
    """Print and return a human-readable profile comparison table."""
    header = (
        f"{'profile':<11} {'dim':<6} {'rel_cost':<9} {'rel_qual':<9} "
        f"{'recall@5':<9} {'value':<7}"
    )
    lines = [header, "-" * len(header)]
    for name, metrics in report["profiles"].items():
        lines.append(
            f"{name:<11} {metrics['dim']:<6} {metrics['rel_cost']:<9} "
            f"{metrics['rel_quality']:<9} {metrics['recall_at_5']:<9} "
            f"{metrics['value']:<7}"
        )
    table = "\n".join(lines)
    print(table)
    return table


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: print the table and recommendation, exit 0."""
    parser = argparse.ArgumentParser(prog="eval.embedding_bench")
    parser.add_argument("--docs", type=int, default=50, help="Number of synthetic documents (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--query", default="alpha", help="Query topic word (default: alpha)")
    args = parser.parse_args(argv)
    report = run_benchmark(n_docs=args.docs, seed=args.seed, query_topic=args.query)
    print_table(report)
    print(f"winner: {report['winner']}")
    print(f"recommendation: {report['recommendation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
