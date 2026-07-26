import pytest

from mcp_cli.services.frontier import (
    extract_citations,
    is_sensitive_tool,
    make_file_paths_clickable,
)


@pytest.mark.parametrize("name,expected", [
    ("write_file", True),
    ("edit_document", True),
    ("delete_entities", True),
    ("move_file", True),
    ("copy_file", True),
    ("create_directory", True),
    ("add_entities", True),
    ("read_file", False),
    ("search_resources", False),
    ("list_directory", False),
    ("echo", False),
    ("get_weather", False),
])
def test_is_sensitive_tool(name, expected):
    assert is_sensitive_tool(name) is expected


def test_make_file_paths_clickable():
    text = "See /workspace/docs/report.pdf for details"
    result = make_file_paths_clickable(text)
    assert "[/docs/report.pdf](/docs/report.pdf)" in result


def test_make_file_paths_clickable_no_paths():
    text = "Just a normal message with no file paths"
    result = make_file_paths_clickable(text)
    assert result == text


def test_make_file_paths_clickable_multiple():
    text = "Found /docs/a.pdf and /docs/b.txt"
    result = make_file_paths_clickable(text)
    assert "](/a.pdf)" in result
    assert "](/b.txt)" in result


def test_extract_citations():
    results = [
        {"name": "read_document", "args": {"doc_id": "report.pdf"}, "result": "Annual report content"},
        {"name": "search_resources", "args": {"query": "budget"}, "result": "budget.xlsx"},
        {"name": "write_file", "args": {}, "result": "File written"},
    ]
    citations = extract_citations("some text", results)
    assert len(citations) == 2
    assert citations[0]["tool"] == "read_document"


def test_extract_citations_skips_errors():
    results = [
        {"name": "read_document", "args": {"doc_id": "x"}, "result": "Tool error: not found"},
    ]
    citations = extract_citations("text", results)
    assert len(citations) == 0



