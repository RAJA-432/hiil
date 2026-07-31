"""Export chat history from the messages table to OpenAI-style training JSONL.

Usage:
    python scripts/export_training_data.py --db chat_history.db --out training_data.jsonl
    python scripts/export_training_data.py --db chat_history.db --split --train-ratio 0.9
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path
from typing import Any

DEFAULT_DB = "chat_history.db"
DEFAULT_OUT = "training_data.jsonl"


def _tool_call_id(message_id: int, content: str) -> str:
    """Derive a stable tool_call_id for a tool-role message."""
    try:
        data = json.loads(content)
    except ValueError:
        return f"tool_call_{message_id}"
    if isinstance(data, dict) and data.get("tool_call_id"):
        return str(data["tool_call_id"])
    return f"tool_call_{message_id}"


def _assistant_tool_calls(content: str) -> list[Any] | None:
    """Extract a tool_calls list from JSON-stored assistant content, if any."""
    try:
        data = json.loads(content)
    except ValueError:
        return None
    if isinstance(data, dict) and isinstance(data.get("tool_calls"), list):
        return data["tool_calls"]
    return None


def read_sessions(db_path: str, min_messages: int = 2) -> list[tuple[str, list[dict[str, Any]]]]:
    """Read messages from the database, grouped into sessions.

    Returns (session_id, messages) pairs ordered by first message id, where
    messages within a session are ordered by timestamp then id ascending.
    """
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"database not found: {db}")
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT id, session_id, role, content, timestamp FROM messages ORDER BY timestamp ASC, id ASC"
        ).fetchall()
    finally:
        conn.close()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row_id, session_id, role, content, timestamp in rows:
        grouped.setdefault(session_id, []).append(
            {
                "id": row_id,
                "role": role or "",
                "content": content or "",
                "timestamp": timestamp or "",
            }
        )
    sessions: list[tuple[str, list[dict[str, Any]]]] = []
    for session_id, messages in grouped.items():
        if len(messages) < min_messages:
            continue
        messages.sort(key=lambda m: (m["timestamp"], m["id"]))
        sessions.append((session_id, messages))
    sessions.sort(key=lambda item: item[1][0]["id"])
    return sessions


def build_examples(
    sessions: list[tuple[str, list[dict[str, Any]]]],
    include_tool_calls: bool = False,
) -> list[dict[str, Any]]:
    """Convert (session_id, messages) pairs into OpenAI-style training examples."""
    examples: list[dict[str, Any]] = []
    for _session_id, messages in sessions:
        conversation: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg["role"], "content": msg["content"]}
            if msg["role"] == "tool":
                entry["tool_call_id"] = _tool_call_id(msg["id"], msg["content"])
            elif msg["role"] == "assistant" and include_tool_calls:
                calls = _assistant_tool_calls(msg["content"])
                if calls is not None:
                    entry["tool_calls"] = calls
            conversation.append(entry)
        examples.append({"messages": conversation})
    return examples


def export_sessions(
    db_path: str,
    min_messages: int = 2,
    include_tool_calls: bool = False,
) -> list[dict[str, Any]]:
    """Load history from a database and build training examples."""
    return build_examples(read_sessions(db_path, min_messages), include_tool_calls)


def write_examples(examples: list[dict[str, Any]], out_path: str | Path) -> Path:
    """Write one JSON object per line to out_path."""
    out = Path(out_path)
    lines = [json.dumps(example, ensure_ascii=False) for example in examples]
    text = "\n".join(lines)
    if text:
        text += "\n"
    out.write_text(text, encoding="utf-8")
    return out


def write_split(
    examples: list[dict[str, Any]],
    out_path: str | Path,
    train_ratio: float = 0.9,
    seed: int = 0,
) -> tuple[Path, Path]:
    """Shuffle examples with a seeded RNG and write train/val JSONL files."""
    shuffled = list(examples)
    random.Random(seed).shuffle(shuffled)
    n_train = round(len(shuffled) * train_ratio)
    train, val = shuffled[:n_train], shuffled[n_train:]
    base = Path(out_path)
    train_path = base.with_name(f"{base.stem}.train.jsonl")
    val_path = base.with_name(f"{base.stem}.val.jsonl")
    write_examples(train, train_path)
    write_examples(val, val_path)
    return train_path, val_path


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.open(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="export_training_data",
        description="Export chat history to OpenAI-style training JSONL.",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite history database (default: {DEFAULT_DB})")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"Output JSONL path (default: {DEFAULT_OUT})")
    parser.add_argument("--min-messages", type=int, default=2, help="Skip sessions with fewer messages (default: 2)")
    parser.add_argument(
        "--include-tool-calls",
        action="store_true",
        help="Export tool_calls from JSON-stored assistant content",
    )
    parser.add_argument("--split", action="store_true", help="Write seeded train/val splits instead of a single file")
    parser.add_argument("--train-ratio", type=float, default=0.9, help="Fraction of sessions for the train split (default: 0.9)")
    parser.add_argument("--seed", type=int, default=0, help="Seed for the split shuffle (default: 0)")
    args = parser.parse_args(argv)

    if not 0.0 < args.train_ratio < 1.0:
        print(f"error: --train-ratio must be between 0 and 1, got {args.train_ratio}", file=sys.stderr)
        return 2

    try:
        examples = export_sessions(args.db, min_messages=args.min_messages, include_tool_calls=args.include_tool_calls)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    total_messages = sum(len(example["messages"]) for example in examples)
    if args.split:
        train_path, val_path = write_split(examples, args.out, args.train_ratio, args.seed)
        print(f"exported {len(examples)} sessions ({total_messages} messages)")
        print(f"train: {_count_lines(train_path)} sessions -> {train_path}")
        print(f"val: {_count_lines(val_path)} sessions -> {val_path}")
    else:
        out_path = write_examples(examples, args.out)
        print(f"exported {len(examples)} sessions ({total_messages} messages) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
