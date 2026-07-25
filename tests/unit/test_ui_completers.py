from unittest.mock import MagicMock

from prompt_toolkit.document import Document

from mcp_cli.ui.completers import HiilCompleter


def _doc(text, cursor_pos=None):
    return Document(text=text, cursor_position=cursor_pos if cursor_pos is not None else len(text))


def _make_completer(chat=None, app=None):
    c = chat or MagicMock()
    if chat is None:
        c.doc_ids = []
        c.tools_by_name = {}
        c.clients = {}
        c.session_id = "default"
    a = app or MagicMock()
    a._theme.name = "opencode"
    comp = HiilCompleter(c, a)
    comp.set_metadata()
    return comp


def test_no_match_returns_empty():
    comp = _make_completer()
    doc = _doc("hello world")
    results = list(comp.get_completions(doc, None))
    assert len(results) == 0


def test_doc_completion_matches_prefix():
    chat = MagicMock()
    chat.doc_ids = ["deposition", "report", "spec"]
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("see @dep")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "deposition" in texts


def test_doc_completion_case_insensitive():
    chat = MagicMock()
    chat.doc_ids = ["MyDoc", "mydoc2"]
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("@MYD")
    results = list(comp.get_completions(doc, None))
    assert len(results) >= 1


def test_doc_completion_at_start_of_line():
    chat = MagicMock()
    chat.doc_ids = ["spec", "notes"]
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("@spe")
    results = list(comp.get_completions(doc, None))
    assert len(results) == 1
    assert results[0].text == "spec"


def test_doc_completion_empty_ids():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("@x")
    results = list(comp.get_completions(doc, None))
    assert len(results) == 0


def test_doc_completion_fuzzy():
    chat = MagicMock()
    chat.doc_ids = ["deposition", "report", "specification"]
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("@sp")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "specification" in texts
    assert "deposition" not in texts


def test_command_list_shows_commands():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("/")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "/help" in texts
    assert "/exit" in texts


def test_command_list_fuzzy():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("/mod")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "/model" in texts
    assert "/models" in texts


def test_subcommand_completions():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("/key ")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "set" in texts
    assert "delete" in texts
    assert "status" in texts


def test_session_completions():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {}
    chat.clients = {}
    chat.history.list_sessions.return_value = ["session1", "session2"]
    chat.session_id = "session1"
    comp = _make_completer(chat)
    doc = _doc("/session ")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "session1" in texts
    assert "session2" in texts


def test_completions_have_display_meta():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {}
    comp = _make_completer(chat)
    doc = _doc("/help")
    results = list(comp.get_completions(doc, None))
    for r in results:
        if r.text == "/help":
            assert r.display_meta
            break


def test_tool_completions():
    chat = MagicMock()
    chat.doc_ids = []
    chat.tools_by_name = {
        "read_file": {
            "openai": {
                "function": {
                    "name": "read_file",
                    "description": "Read a file from disk",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        },
    }
    comp = _make_completer(chat)
    doc = _doc("/read")
    results = list(comp.get_completions(doc, None))
    texts = [c.text for c in results]
    assert "/read_file" in texts
