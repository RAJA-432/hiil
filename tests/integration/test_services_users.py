from unittest.mock import patch

from mcp_cli.services.users import (
    authenticate_user,
    delete_user,
    list_users,
    register_user,
    user_count,
)


def test_register_and_authenticate(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        err = register_user("alice", "secret123")
        assert err is None
        assert authenticate_user("alice", "secret123") is True
        assert authenticate_user("alice", "wrong") is False


def test_register_duplicate(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        register_user("bob", "pass1234")
        err = register_user("bob", "otherpass")
        assert err is not None
        assert "already exists" in err


def test_register_empty_input(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        assert register_user("", "pass") is not None
        assert register_user("user", "") is not None


def test_register_short_password(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        err = register_user("user", "ab")
        assert err is not None
        assert "4 characters" in err


def test_authenticate_nonexistent_user(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        assert authenticate_user("nobody", "pass") is False


def test_list_users(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        register_user("alice", "pass1")
        register_user("bob", "pass2")
        users = list_users()
        assert "alice" in users
        assert "bob" in users


def test_delete_user(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        register_user("alice", "pass1")
        assert delete_user("alice") is True
        assert authenticate_user("alice", "pass1") is False


def test_delete_nonexistent_user(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        assert delete_user("nobody") is False


def test_user_count(tmp_path):
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        assert user_count() == 0
        register_user("alice", "pass1")
        assert user_count() == 1
        register_user("bob", "pass2")
        assert user_count() == 2


def test_password_hashing_different_salts(tmp_path):
    import sqlite3
    db_path = tmp_path / "users.db"
    with patch("mcp_cli.services.users._DB_PATH", db_path):
        register_user("u1", "samepass")
        register_user("u2", "samepass")
        db = sqlite3.connect(str(db_path))
        rows = db.execute("SELECT salt FROM users ORDER BY username").fetchall()
        db.close()
        assert rows[0][0] != rows[1][0]
