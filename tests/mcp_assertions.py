from __future__ import annotations

from mcp_server.storage.store import docs


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


def run_mcp_setup(case: dict) -> dict | None:
    setup = case.get("setup")
    if setup and "save_doc" in setup:
        doc_id = setup["save_doc"]
        return {doc_id: docs.get(doc_id, "")}
    return None


def run_mcp_teardown(case: dict, saved: dict | None) -> None:
    teardown = case.get("teardown")
    if teardown and "restore_doc" in teardown and saved:
        doc_id = teardown["restore_doc"]
        if doc_id in saved:
            docs[doc_id] = saved[doc_id]
