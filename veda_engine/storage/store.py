from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path.home() / ".hiil"
DB_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _db_path(user_id: str) -> Path:
    return DB_DIR / f"docs_{user_id}.db"


def _get_conn(user_id: str = "default") -> sqlite3.Connection:
    db_path = _db_path(user_id)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS documents ("
        "  id TEXT PRIMARY KEY,"
        "  content TEXT NOT NULL"
        ")"
    )
    conn.commit()
    return conn


def get_document(doc_id: str, user_id: str = "default") -> str:
    conn = _get_conn(user_id)
    try:
        row = conn.execute(
            "SELECT content FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Document {doc_id} not found")
        return row["content"]
    finally:
        conn.close()


def edit_document(doc_id: str, old_str: str, new_str: str, user_id: str = "default") -> str:
    conn = _get_conn(user_id)
    try:
        row = conn.execute(
            "SELECT content FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Document {doc_id} not found")
        content = row["content"]
        if old_str not in content:
            raise ValueError(f"'{old_str}' not found in document {doc_id}")
        updated = content.replace(old_str, new_str)
        conn.execute("UPDATE documents SET content = ? WHERE id = ?", (updated, doc_id))
        conn.commit()
        return updated
    finally:
        conn.close()


def create_document(doc_id: str, content: str, user_id: str = "default") -> str:
    conn = _get_conn(user_id)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO documents (id, content) VALUES (?, ?)",
            (doc_id, content),
        )
        conn.commit()
        return content
    finally:
        conn.close()


def put_document(doc_id: str, content: str, user_id: str = "default") -> None:
    create_document(doc_id, content, user_id=user_id)


def list_document_ids(user_id: str = "default") -> list[str]:
    conn = _get_conn(user_id)
    try:
        rows = conn.execute("SELECT id FROM documents ORDER BY id").fetchall()
        return [r["id"] for r in rows]
    finally:
        conn.close()


def get_document_info(doc_id: str, user_id: str = "default") -> dict:
    conn = _get_conn(user_id)
    try:
        row = conn.execute(
            "SELECT id, content FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Document {doc_id} not found")
        filename = row["id"].split("/")[-1] if "/" in row["id"] else row["id"]
        return {"id": row["id"], "filename": filename, "content": row["content"]}
    finally:
        conn.close()


def list_document_info(user_id: str = "default") -> list[dict]:
    conn = _get_conn(user_id)
    try:
        rows = conn.execute("SELECT id, content FROM documents ORDER BY id").fetchall()
        result = []
        for r in rows:
            filename = r["id"].split("/")[-1] if "/" in r["id"] else r["id"]
            result.append({"id": r["id"], "filename": filename, "content": r["content"]})
        return result
    finally:
        conn.close()


def reset_store(user_id: str = "default"):
    conn = _get_conn(user_id)
    try:
        conn.execute("DELETE FROM documents")
        conn.commit()
    finally:
        conn.close()
