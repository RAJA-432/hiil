from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

_DB_PATH = Path.home() / ".hiil" / "users.db"


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH))
    db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "  username TEXT PRIMARY KEY,"
        "  salt TEXT NOT NULL,"
        "  hash TEXT NOT NULL"
        ")"
    )
    db.commit()
    return db


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1, dklen=32)
    return salt, h.hex()


def register_user(username: str, password: str) -> str | None:
    """Create a new user account; return an error message on failure or None on success."""
    if not username.strip() or not password.strip():
        return "Username and password are required."
    if len(password) < 4:
        return "Password must be at least 4 characters."
    db = _get_db()
    try:
        existing = db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return f"User '{username}' already exists."
        salt, h = _hash_password(password)
        db.execute("INSERT INTO users (username, salt, hash) VALUES (?, ?, ?)", (username, salt, h))
        db.commit()
        return None
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> bool:
    """Verify a username and password against the stored hash; return True on match."""
    db = _get_db()
    try:
        row = db.execute("SELECT salt, hash FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return False
        salt, stored_hash = row
        _, computed_hash = _hash_password(password, salt)
        return computed_hash == stored_hash
    finally:
        db.close()


def list_users() -> list[str]:
    """Return a sorted list of all registered usernames."""
    db = _get_db()
    try:
        rows = db.execute("SELECT username FROM users ORDER BY username").fetchall()
        return [r[0] for r in rows]
    finally:
        db.close()


def delete_user(username: str) -> bool:
    """Delete a user account and return True if the user existed."""
    db = _get_db()
    try:
        cur = db.execute("DELETE FROM users WHERE username = ?", (username,))
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def user_count() -> int:
    """Return the total number of registered users."""
    db = _get_db()
    try:
        return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        db.close()
