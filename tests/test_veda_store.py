from __future__ import annotations

import re

import pytest

from veda_engine.storage import store


def test_sanitize_keeps_safe_ids_readable():
    for user_id in ("default", "alice", "alice_bob-42", "a.b"):
        assert store._sanitize_user_id(user_id) == user_id


@pytest.mark.parametrize(
    "user_id",
    ["../../etc", "foo/bar", "a\\b", "..\\..\\x", "..", ".", "...", "with\x00nul"],
)
def test_sanitize_neutralizes_unsafe_ids(user_id):
    safe = store._sanitize_user_id(user_id)
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", safe)
    assert "/" not in safe
    assert "\\" not in safe
    assert "\x00" not in safe
    assert safe not in (".", "..")


def test_sanitize_is_deterministic_and_distinct():
    assert store._sanitize_user_id("../../etc") == store._sanitize_user_id("../../etc")
    assert store._sanitize_user_id("a/b") != store._sanitize_user_id("a\\b")


def test_sanitize_truncates_overlong_ids():
    safe = store._sanitize_user_id("x" * 200)
    assert len(safe) <= 64 + 13


def test_sanitize_rejects_empty():
    with pytest.raises(ValueError):
        store._sanitize_user_id("")


@pytest.mark.parametrize("user_id", ["../../etc", "foo/bar", "a\\b", "..\\..\\x", "with\x00nul"])
def test_db_path_stays_inside_db_dir(tmp_path, monkeypatch, user_id):
    monkeypatch.setattr(store, "DB_DIR", tmp_path)
    db_path = store._db_path(user_id)
    assert db_path.parent == tmp_path
    assert db_path.name.startswith("docs_")
    assert db_path.name.endswith(".db")
    assert ".." not in db_path.parts


def test_document_store_roundtrip_with_malicious_user_id(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_DIR", tmp_path)
    store.create_document("d1", "secret content", user_id="../../etc")
    assert store.get_document("d1", user_id="../../etc") == "secret content"
    created = [p for p in tmp_path.iterdir() if p.name.endswith(".db")]
    assert len(created) == 1
