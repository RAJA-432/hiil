import os

from veda_engine.storage.store import create_document, reset_store
from veda_engine.resources.documents import fetch_doc, list_docs

_TEST_USER = "test"


def setup_function():
    os.environ["HIIL_USER_ID"] = _TEST_USER
    reset_store(_TEST_USER)
    create_document("plan.md", "The plan outlines the steps for the project's implementation.", user_id=_TEST_USER)


def teardown_function():
    reset_store(_TEST_USER)
    os.environ.pop("HIIL_USER_ID", None)


def test_list_docs():
    ids = list_docs()
    assert len(ids) == 1
    assert "plan.md" in ids


def test_fetch_doc():
    content = fetch_doc("plan.md")
    assert "project" in content


def test_fetch_doc_not_found():
    try:
        fetch_doc("ghost.txt")
        assert False, "expected ValueError"
    except ValueError:
        pass
