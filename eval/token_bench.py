"""Hermetic RAG context-budget benchmark.

Compares two context-assembly budgets against a synthetic corpus:

* ``206-budget`` — ``max_tokens=512`` minus a 306-token output reserve.
* ``4k-budget``  — ``max_tokens=4096`` minus a 1024-token output reserve.

Chunks are generated from the synthetic corpus and then greedily packed in
order, mirroring the accumulation step in ``RagPipeline.retrieve_compressed``.
Metrics per config: coverage (chunks that fit) and overhead (context tokens
used vs. total source tokens), folded into a single ``score``.

No LLM, embeddings, or servers are involved, so it can run in CI.
``mcp_cli.services.prompt_budget`` is used for token estimation when available;
otherwise the benchmark falls back to a local word-count estimator — the same
heuristic ``RagPipeline.estimated_tokens`` already uses.

Usage: ``python -m eval.token_bench [--docs 20] [--seed 42]``
"""

from __future__ import annotations

import argparse
import random
import sys

try:
    from mcp_cli.services.chunker import chunk_by_content as _chunk_by_content
except ImportError:  # pragma: no cover - fallback path when chunker is unavailable
    _chunk_by_content = None

try:
    from mcp_cli.services.prompt_budget import estimate_tokens as _pb_estimate_tokens
except ImportError:  # pragma: no cover - module is added in parallel
    _pb_estimate_tokens = None

SMALL = {"max_tokens": 512, "reserve_output": 306, "name": "206-budget"}
LARGE = {"max_tokens": 4096, "reserve_output": 1024, "name": "4k-budget"}
CONFIGS = (SMALL, LARGE)

_DOC_WORDS = 80
_CHUNK_SIZE = 512
_CHUNK_OVERLAP = 50
_WORD_POOL = [
    "context", "retrieval", "token", "budget", "chunk", "embedding",
    "vector", "store", "query", "document", "corpus", "assembly",
    "overlap", "reserve", "ceiling", "index", "score", "relevance",
    "latency", "throughput", "coverage", "overhead", "scale", "ranking",
]


def estimate_tokens(text: str) -> int:
    """Return a deterministic token estimate for ``text``.

    Prefers ``prompt_budget``'s estimator when the (parallel) module is
    importable; otherwise falls back to a word count, matching the heuristic
    used by ``RagPipeline.estimated_tokens``.
    """
    if _pb_estimate_tokens is not None:
        try:
            estimate = int(_pb_estimate_tokens(text))
            if estimate > 0:
                return estimate
        except Exception:
            pass
    return max(1, len(text.split()))


def make_corpus(n_docs: int = 20, seed: int = 42) -> list[str]:
    """Build ``n_docs`` deterministic prose-like documents of ~80 words each."""
    rng = random.Random(seed)
    docs: list[str] = []
    for doc_index in range(n_docs):
        words = [f"{rng.choice(_WORD_POOL)}{doc_index}_{i}" for i in range(_DOC_WORDS)]
        docs.append(" ".join(words))
    return docs


def _chunk_by_words_fallback(text: str) -> list[dict[str, object]]:
    """Word-window chunker replicating ``chunk_by_tokens`` behaviour."""
    words = text.split()
    if not words:
        return []
    chunks: list[dict[str, object]] = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_SIZE, len(words))
        chunks.append({"text": " ".join(words[start:end])})
        if end == len(words):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def chunk_corpus(docs: list[str]) -> list[dict[str, object]]:
    """Chunk every document, using the project chunker when available."""
    chunks: list[dict[str, object]] = []
    for doc in docs:
        if _chunk_by_content is not None:
            try:
                chunks.extend(_chunk_by_content(doc, default_size=_CHUNK_SIZE, overlap=_CHUNK_OVERLAP))
                continue
            except Exception:
                pass
        chunks.extend(_chunk_by_words_fallback(doc))
    return chunks


def simulate_assembly(chunks: list[dict[str, object]], budget: int) -> tuple[list[dict[str, object]], int]:
    """Greedily pack chunks in order until the token budget is consumed."""
    fitted: list[dict[str, object]] = []
    used = 0
    for chunk in chunks:
        size = estimate_tokens(str(chunk.get("text", "")))
        if used + size > budget:
            break
        fitted.append(chunk)
        used += size
    return fitted, used


def compute_metrics(
    config: dict[str, float | int],
    chunks: list[dict[str, object]],
    n_docs: int,
    source_tokens: int,
) -> dict[str, float | int]:
    """Compute coverage / overhead / score metrics for a single budget config."""
    budget = int(config["max_tokens"] - config["reserve_output"])
    fitted, used = simulate_assembly(chunks, budget)
    chunks_total = len(chunks)
    chunks_fit = len(fitted)
    coverage = chunks_fit / chunks_total if chunks_total else 0.0
    overhead = used / source_tokens if source_tokens else 0.0
    return {
        "documents": n_docs,
        "chunks_total": chunks_total,
        "chunks_fit": chunks_fit,
        "context_tokens_used": used,
        "budget": budget,
        "coverage_pct": round(coverage, 4),
        "overhead_pct": round(overhead, 4),
        "score": round(coverage * (1 - overhead), 4),
    }


def _recommendation(
    configs: dict[str, dict[str, float | int]],
    winner: str,
    n_docs: int,
    source_tokens: int,
) -> str:
    """Turn the winner into an actionable, practical recommendation."""
    winning = configs[winner]
    losing_name = next(name for name in configs if name != winner)
    losing = configs[losing_name]
    if winner == "206-budget":
        return (
            f"For a {n_docs}-doc corpus (~{source_tokens} tokens) the 206-token budget "
            f"is the more token-efficient pick (score {winning['score']:.3f}): it fits "
            f"{winning['chunks_fit']} chunks at only {winning['overhead_pct']:.0%} of the "
            f"source, while {losing_name} still fits {losing['chunks_fit']}. Adopt the 4k "
            "budget as the corpus grows past the small budget's reach."
        )
    return (
        f"For a {n_docs}-doc corpus (~{source_tokens} tokens) the 4k budget wins "
        f"(score {winning['score']:.3f}): it fits {winning['chunks_fit']}/{winning['chunks_total']} "
        f"chunks ({winning['coverage_pct']:.0%}) that the 206-token budget cannot reach. "
        "Watch overhead as the corpus approaches the full budget."
    )


def run_benchmark(n_docs: int = 20, seed: int = 42) -> dict[str, object]:
    """Run the two-budget comparison; return configs, winner, recommendation."""
    chunks = chunk_corpus(make_corpus(n_docs, seed))
    source_tokens = sum(estimate_tokens(str(c.get("text", ""))) for c in chunks)
    configs: dict[str, dict[str, float | int]] = {}
    for config in CONFIGS:
        configs[config["name"]] = compute_metrics(config, chunks, n_docs, source_tokens)
    winner = max(configs, key=lambda name: configs[name]["score"])
    return {
        "configs": configs,
        "winner": winner,
        "recommendation": _recommendation(configs, winner, n_docs, source_tokens),
    }


def print_table(report: dict[str, object]) -> str:
    """Print and return a human-readable comparison table."""
    configs: dict[str, dict[str, float | int]] = report["configs"]
    header = (
        f"{'config':<12} {'budget':<7} {'docs':<5} {'total':<7} "
        f"{'fit':<5} {'coverage':<9} {'overhead':<9} {'score':<7}"
    )
    lines = [header, "-" * len(header)]
    for name, metrics in configs.items():
        lines.append(
            f"{name:<12} {metrics['budget']:<7} {metrics['documents']:<5} "
            f"{metrics['chunks_total']:<7} {metrics['chunks_fit']:<5} "
            f"{metrics['coverage_pct']:<9} {metrics['overhead_pct']:<9} "
            f"{metrics['score']:<7}"
        )
    table = "\n".join(lines)
    print(table)
    return table


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: print the table and recommendation, exit 0."""
    parser = argparse.ArgumentParser(prog="eval.token_bench")
    parser.add_argument("--docs", type=int, default=20, help="Number of synthetic documents (default: 20)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the corpus (default: 42)")
    args = parser.parse_args(argv)
    report = run_benchmark(n_docs=args.docs, seed=args.seed)
    print_table(report)
    print(f"winner: {report['winner']}")
    print(f"recommendation: {report['recommendation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
