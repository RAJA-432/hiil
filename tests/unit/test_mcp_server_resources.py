from mcp_server.resources.documents import fetch_doc, list_docs


def test_list_docs():
    ids = list_docs()
    assert len(ids) == 6
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
