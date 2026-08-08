"""Hermetic retrieval-quality (F1) evaluation harness.

Measures how well RAG retrieval surfaces relevant chunks for a query against
the "user validation with long documents" task, without any network access or
real embeddings. A deterministic synthetic bag-of-words embedding replaces the
embedding model so the harness runs in CI.

Usage: ``python -m eval.retrieval_f1 [--docs 20] [--seed 42] [--top-k 5] [--backend sqlite|faiss] [--tmp-dir PATH]``
"""

from __future__ import annotations

import argparse
import math
import random
import re
import sys
import tempfile
import zlib
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any

try:
    from mcp_cli.services.chunker import chunk_by_content, chunk_by_tokens
except ImportError:  # pragma: no cover - fallback when chunker is unavailable
    chunk_by_content = None
    chunk_by_tokens = None

try:
    from mcp_cli.services.vector_store import create_vector_store
except ImportError:  # pragma: no cover - fallback when vector store is unavailable
    create_vector_store = None

_NAMESPACE = "documents"
_EMBED_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_TOPIC_PREFIXES = ("zor", "kel", "pha", "mur", "dax", "vix", "quel", "bram", "thor", "lym", "solv", "pyr")
_TOPIC_SUFFIXES = ("va", "mir", "an", "et", "or", "ux", "il", "ax", "on", "is", "en", "ar")


def synthetic_embedding(text: str, seed: int = 0) -> list[float]:
    """Return a deterministic bag-of-words-style embedding, normalized to unit length.

    The text is lower-cased and split on non-alphanumeric characters. Every word
    is hashed (deterministically, independent of ``PYTHONHASHSEED``) into one of
    ``_EMBED_DIM`` buckets, and its frequency count is scaled by a per-bucket
    weight drawn from a seeded RNG. Empty or punctuation-only text yields the
    zero vector (zero-length safe).
    """
    rng = random.Random(seed)
    weights = [0.5 + rng.random() for _ in range(_EMBED_DIM)]
    vector = [0.0] * _EMBED_DIM
    for word in _TOKEN_RE.findall(text.lower()):
        bucket = (zlib.crc32(word.encode("utf-8")) ^ seed) % _EMBED_DIM
        vector[bucket] += weights[bucket]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return [0.0] * _EMBED_DIM
    return [value / norm for value in vector]


def label_relevant(doc: dict[str, Any], query: str) -> bool:
    """Return True when any of ``doc``'s topic signal words appears in ``query``."""
    query_lower = query.lower()
    for topic in doc.get("topic") or []:
        if str(topic).lower() in query_lower:
            return True
    return False


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    """Chunk ``text`` with the project chunker, falling back defensively."""
    if not text:
        return []
    if chunk_by_content is not None:
        try:
            return chunk_by_content(text, default_size=chunk_size, overlap=overlap)
        except Exception:
            pass
    if chunk_by_tokens is not None:
        return chunk_by_tokens(text, chunk_size=chunk_size, overlap=overlap)
    return [{"text": text}]


def build_index(
    docs: list[dict[str, Any]],
    backend: str = "sqlite",
    db_path: str | None = None,
    chunk_size: int = 512,
    overlap: int = 50,
) -> tuple[Any, dict[str, Any]]:
    """Chunk every ``docs`` entry and index each chunk into a vector store.

    Each chunk is embedded with :func:`synthetic_embedding` and stored with
    metadata ``{"doc_id", "title", "chunk_index", "filename"}``. Returns
    ``(store, {"doc_ids": [...], "chunks_total": int})``; the caller owns the
    store and is responsible for calling ``close()``.
    """
    if create_vector_store is None:  # pragma: no cover - only when mcp_cli is missing
        raise RuntimeError("mcp_cli.services.vector_store is unavailable")
    store = create_vector_store(backend, db_path)
    doc_ids: list[str] = []
    chunks_total = 0
    for doc in docs:
        doc_id = str(doc.get("id", ""))
        doc_ids.append(doc_id)
        title = str(doc.get("title", ""))
        for index, chunk in enumerate(_chunk_text(str(doc.get("content", "")), chunk_size, overlap)):
            text = str(chunk.get("text", ""))
            if not text:
                continue
            store.index(
                namespace=_NAMESPACE,
                key=f"{doc_id}#chunk_{index}",
                text=text,
                embedding=synthetic_embedding(text),
                metadata={"doc_id": doc_id, "title": title, "chunk_index": index, "filename": doc_id},
            )
            chunks_total += 1
    return store, {"doc_ids": doc_ids, "chunks_total": chunks_total}


def run_f1(
    query: str,
    store: Any,
    docs: list[dict[str, Any]],
    top_k: int = 5,
    label_fn: Callable[[dict[str, Any], str], bool] = label_relevant,
) -> dict[str, Any]:
    """Score retrieval for a single ``query`` against a built ``store``.

    ``docs`` is the full document list (each dict carrying ``id`` and ``topic``)
    used to derive the relevant set via ``label_fn``. Returns
    ``{"precision", "recall", "f1", "retrieved_count", "relevant_count", "hits"}``.
    """
    if store.count(_NAMESPACE) == 0:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "retrieved_count": 0,
            "relevant_count": 0,
            "hits": 0,
        }
    relevant = {str(doc.get("id")) for doc in docs if label_fn(doc, query)}
    results = store.search(synthetic_embedding(query), namespace=_NAMESPACE, limit=top_k)
    retrieved = {str(result.get("metadata", {}).get("doc_id", "")) for result in results}
    hits = retrieved & relevant
    retrieved_count = len(retrieved)
    relevant_count = len(relevant)
    hits_count = len(hits)
    precision = hits_count / retrieved_count if retrieved_count else 0.0
    recall = hits_count / relevant_count if relevant_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "retrieved_count": retrieved_count,
        "relevant_count": relevant_count,
        "hits": hits_count,
    }


def run_validation(
    docs: list[dict[str, Any]],
    queries: list[str],
    top_k: int = 5,
    backend: str = "sqlite",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Build one index and aggregate per-query P/R/F1 across ``queries``.

    ``db_path`` defaults to a self-cleaning temporary database so the harness
    never touches the user's ``~/.hiil/vectors.db``.
    """
    with nullcontext(None) if db_path is not None else tempfile.TemporaryDirectory(prefix="hiil_retrieval_f1_") as tmp:
        path = db_path if db_path is not None else str(Path(tmp) / "vectors.db")  # type: ignore[arg-type]
        store, stats = build_index(docs, backend=backend, db_path=path)
        try:
            per_query = [run_f1(query, store, docs, top_k=top_k) for query in queries]
        finally:
            store.close()
    count = len(per_query)
    rows = [
        {"query": query, "precision": row["precision"], "recall": row["recall"], "f1": row["f1"]}
        for query, row in zip(queries, per_query)
    ]
    return {
        "mean_precision": sum(row["precision"] for row in rows) / count if count else 0.0,
        "mean_recall": sum(row["recall"] for row in rows) / count if count else 0.0,
        "mean_f1": sum(row["f1"] for row in rows) / count if count else 0.0,
        "per_query": rows,
        "chunks_total": stats["chunks_total"],
        "doc_count": len(docs),
    }


def make_topic_word(rng: random.Random) -> str:
    """Build one distinctive, deterministic made-up topic signal word."""
    return f"{rng.choice(_TOPIC_PREFIXES)}{rng.choice(_TOPIC_SUFFIXES)}"


def make_document(doc_index: int, topic: list[str], rng: random.Random, words: int = 120) -> str:
    """Build a ~``words``-word document that repeats its topic words plus unique filler."""
    topic = list(topic) or [f"topic{doc_index}"]
    tokens: list[str] = []
    for i in range(words):
        if i % 10 < 3:
            tokens.append(topic[i % len(topic)])
        else:
            tokens.append(f"term{doc_index}_{i}")
    return " ".join(tokens)


def make_corpus(n_docs: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Build ``n_docs`` deterministic long documents with topic words and filler.

    Doc 1 deliberately shares doc 0's topic so queries can have multiple
    relevant documents.
    """
    rng = random.Random(seed)
    docs: list[dict[str, Any]] = []
    for i in range(n_docs):
        topic = [make_topic_word(rng) for _ in range(3)]
        if i == 1:
            topic = list(docs[0]["topic"])
        docs.append(
            {
                "id": f"doc{i}",
                "title": f"Report {i + 1}",
                "content": make_document(i, topic, rng, words=120),
                "topic": topic,
            }
        )
    return docs


def make_queries(docs: list[dict[str, Any]], n_queries: int = 8, seed: int = 1) -> list[str]:
    """Build one query per sampled document, each referencing that doc's topic."""
    if not docs:
        return []
    rng = random.Random(seed)
    indices = rng.sample(range(len(docs)), min(n_queries, len(docs)))
    queries: list[str] = []
    for index in indices:
        topic = docs[index]["topic"]
        first = str(topic[0])
        second = str(topic[1]) if len(topic) > 1 else first
        queries.append(f"What does the report say about {first} and {second}?")
    return queries


def print_table(report: dict[str, Any]) -> str:
    """Print and return a human-readable per-query P/R/F1 table."""
    header = f"{'query':<46} {'precision':<10} {'recall':<8} {'f1':<8}"
    lines = [header, "-" * len(header)]
    for row in report["per_query"]:
        query = row["query"]
        short = query if len(query) <= 44 else query[:41] + "..."
        lines.append(f"{short:<46} {row['precision']:<10.4f} {row['recall']:<8.4f} {row['f1']:<8.4f}")
    lines.append("-" * len(header))
    lines.append(
        f"{'MEAN':<46} {report['mean_precision']:<10.4f} {report['mean_recall']:<8.4f} {report['mean_f1']:<8.4f}"
    )
    lines.append(f"docs={report['doc_count']}  chunks_total={report['chunks_total']}")
    table = "\n".join(lines)
    print(table)
    return table


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: build a synthetic corpus, run validation, print the table."""
    parser = argparse.ArgumentParser(prog="eval.retrieval_f1")
    parser.add_argument("--docs", type=int, default=20, help="Number of synthetic documents (default: 20)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the corpus (default: 42)")
    parser.add_argument("--top-k", type=int, default=5, help="Documents retrieved per query (default: 5)")
    parser.add_argument("--backend", choices=["sqlite", "faiss"], default="sqlite", help="Vector store backend (default: sqlite)")
    parser.add_argument("--tmp-dir", default=None, help="Directory for the temporary vector DB (default: a fresh temp dir)")
    args = parser.parse_args(argv)
    docs = make_corpus(n_docs=args.docs, seed=args.seed)
    queries = make_queries(docs, n_queries=8, seed=args.seed + 1)
    db_path: str | None = None
    if args.tmp_dir is not None:
        out_dir = Path(args.tmp_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(out_dir / "vectors.db")
    report = run_validation(docs, queries, top_k=args.top_k, backend=args.backend, db_path=db_path)
    print_table(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
