from __future__ import annotations

from veda_engine.storage.store import get_document, put_document


def assert_mcp_result(case: dict, result) -> None:
    expect = case.get("expect", {})
    content = getattr(result, "content", [])
    text = " ".join(getattr(b, "text", "") for b in (content or []))

    if "tool_names" in expect:
        names = [t.name for t in result]
        for tool in expect["tool_names"]:
            assert tool in names, f"Expected tool {tool} not in {names}"
    if "min_count" in expect:
        assert len(result) >= expect["min_count"]
    if "uri_contains" in expect:
        uris = [str(r.uri) for r in (result or [])]
        assert any(expect["uri_contains"] in u for u in uris)
    if expect.get("allow_empty") and not text.strip():
        return
    if "contains" in expect:
        assert expect["contains"] in result
    if "text_contains" in expect:
        assert expect["text_contains"] in text
    if "text_contains_any" in expect:
        assert any(s in text for s in expect["text_contains_any"]), (
            f"Expected one of {expect['text_contains_any']} in {text!r}"
        )


_TEST_USER = "test"


def run_mcp_setup(case: dict) -> dict | None:
    setup = case.get("setup")
    if not setup:
        return None
    saved = {}
    if "save_doc" in setup:
        doc_id = setup["save_doc"]
        try:
            saved[doc_id] = get_document(doc_id, _TEST_USER)
        except ValueError:
            saved[doc_id] = ""
    if "put_doc" in setup:
        for doc_id, content in setup["put_doc"].items():
            saved[doc_id] = ""
            try:
                saved[doc_id] = get_document(doc_id, _TEST_USER)
            except ValueError:
                pass
            put_document(doc_id, content, _TEST_USER)
    return saved if saved else None


def run_mcp_teardown(case: dict, saved: dict | None) -> None:
    if not saved:
        return
    teardown = case.get("teardown")
    restore = (teardown or {}).get("restore_doc", [])
    if isinstance(restore, str):
        restore = [restore]
    for doc_id in restore:
        if doc_id in saved:
            if saved[doc_id]:
                put_document(doc_id, saved[doc_id], _TEST_USER)
            else:
                try:
                    put_document(doc_id, "", _TEST_USER)
                except Exception:
                    pass
