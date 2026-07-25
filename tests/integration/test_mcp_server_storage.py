import pytest

from mcp_server.storage.store import edit_document, get_document, list_document_ids


def test_get_document_exists():
    content = get_document("report.pdf")
    assert "condenser tower" in content


def test_get_document_not_found():
    with pytest.raises(ValueError, match="not found"):
        get_document("nonexistent.pdf")


def test_edit_document_replaces_first_occurrence():
    original = get_document("plan.md")
    result = edit_document("plan.md", "steps", "phases")
    assert "phases" in result
    assert result.count("phases") == 1
    edit_document("plan.md", "phases", "steps")
    assert get_document("plan.md") == original


def test_edit_document_not_found():
    with pytest.raises(ValueError, match="not found"):
        edit_document("ghost.txt", "a", "b")


def test_edit_document_old_str_not_found():
    with pytest.raises(ValueError, match="not found"):
        edit_document("spec.txt", "nonexistent string", "replacement")


def test_list_document_ids():
    ids = list_document_ids()
    assert len(ids) == 6
    assert "deposition.md" in ids
    assert "spec.txt" in ids
