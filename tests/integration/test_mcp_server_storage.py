import pytest

from veda_engine.storage.store import (
    create_document,
    edit_document,
    get_document,
    list_document_ids,
    reset_store,
)

_TEST_USER = "test"


@pytest.fixture(autouse=True)
def clean_store():
    reset_store(_TEST_USER)
    yield
    reset_store(_TEST_USER)


def test_get_document_exists():
    create_document("report.pdf", "The report details the state of a 20m condenser tower.", user_id=_TEST_USER)
    content = get_document("report.pdf", user_id=_TEST_USER)
    assert "condenser tower" in content


def test_get_document_not_found():
    with pytest.raises(ValueError, match="not found"):
        get_document("nonexistent.pdf", user_id=_TEST_USER)


def test_edit_document_replaces_first_occurrence():
    create_document("plan.md", "The plan outlines the steps for the project's implementation.", user_id=_TEST_USER)
    original = get_document("plan.md", user_id=_TEST_USER)
    result = edit_document("plan.md", "steps", "phases", user_id=_TEST_USER)
    assert "phases" in result
    assert result.count("phases") == 1
    edit_document("plan.md", "phases", "steps", user_id=_TEST_USER)
    assert get_document("plan.md", user_id=_TEST_USER) == original


def test_edit_document_not_found():
    with pytest.raises(ValueError, match="not found"):
        edit_document("ghost.txt", "a", "b", user_id=_TEST_USER)


def test_edit_document_old_str_not_found():
    create_document("spec.txt", "spec content", user_id=_TEST_USER)
    with pytest.raises(ValueError, match="not found"):
        edit_document("spec.txt", "nonexistent string", "replacement", user_id=_TEST_USER)


def test_list_document_ids():
    create_document("a.txt", "aaa", user_id=_TEST_USER)
    create_document("b.txt", "bbb", user_id=_TEST_USER)
    create_document("c.txt", "ccc", user_id=_TEST_USER)
    ids = list_document_ids(user_id=_TEST_USER)
    assert len(ids) == 3
    assert "a.txt" in ids
    assert "c.txt" in ids


def test_list_document_ids_empty():
    ids = list_document_ids(user_id=_TEST_USER)
    assert ids == []
