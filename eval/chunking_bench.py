"""Hermetic chunk-overlap A/B benchmark.

Compares chunking configurations (chunk_size + overlap) on two axes:

* **overhead** — total indexed words / source words (redundancy cost).
* **needle preservation** — fraction of needle sentences (placed to straddle
  chunk boundaries) that survive intact in at least one chunk.

No LLM, embeddings, or servers are involved: this only exercises the pure
chunking functions so it can run in CI.

Usage: ``python -m eval.chunking_bench [--chunk-size 512] [--overlaps 0,50,100]``
"""

from __future__ import annotations

import argparse
import sys

from mcp_cli.services.chunker import chunk_by_tokens

_NEEDLE = "NEEDLE-MARKER"


def make_document(words_per_section: int = 200, sections: int = 20) -> str:
    """Build a prose document whose sections are sized to straddle a chunk boundary."""
    parts: list[str] = []
    for s in range(sections):
        parts.append(f"Section {s}.")
        # Keep words on one line so `split()` counts stay deterministic.
        words = " ".join(f"w{s}_{i}" for i in range(words_per_section))
        parts.append(words)
        parts.append(f"{_NEEDLE} fact {s} says the answer is {s} {_NEEDLE}.")
    return "\n".join(parts)


def find_needles(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if _NEEDLE in line]


def run_config(
    text: str,
    chunk_size: int,
    overlap: int,
    needles: list[str],
) -> dict[str, float | int]:
    chunks = chunk_by_tokens(text, chunk_size=chunk_size, overlap=overlap)
    source_words = len(text.split())
    indexed_words = sum(c["word_count"] for c in chunks)
    chunk_texts = [c["text"] for c in chunks]
    preserved = sum(1 for n in needles if any(n in ct for ct in chunk_texts))
    return {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "num_chunks": len(chunks),
        "source_words": source_words,
        "indexed_words": indexed_words,
        "overhead": round(indexed_words / source_words, 3) if source_words else 0.0,
        "needles": len(needles),
        "preserved": preserved,
        "preservation": round(preserved / len(needles), 3) if needles else 0.0,
    }


def compare_configs(
    chunk_size: int = 512,
    overlaps: list[int] | None = None,
    sections: int = 20,
) -> list[dict[str, float | int]]:
    text = make_document(sections=sections)
    needles = find_needles(text)
    return [run_config(text, chunk_size, ov, needles) for ov in (overlaps or [0, 50, 100])]


def print_table(rows: list[dict[str, float | int]]) -> str:
    header = (
        f"{'overlap':<8} {'chunks':<7} {'indexed':<8} {'overhead':<9} "
        f"{'needles':<8} {'preserved':<10} {'preservation':<12}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row['overlap']:<8} {row['num_chunks']:<7} {row['indexed_words']:<8} "
            f"{row['overhead']:<9} {row['needles']:<8} {row['preserved']:<10} "
            f"{row['preservation']:<12}"
        )
    table = "\n".join(lines)
    print(table)
    return table


def _parse_overlaps(raw: str | None) -> list[int]:
    if not raw:
        return [0, 50, 100]
    return [int(x) for x in raw.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.chunking_bench")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--overlaps", default=None, help="Comma-separated overlap values (default: 0,50,100)")
    parser.add_argument("--sections", type=int, default=20)
    args = parser.parse_args(argv)
    rows = compare_configs(
        chunk_size=args.chunk_size,
        overlaps=_parse_overlaps(args.overlaps),
        sections=args.sections,
    )
    print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
