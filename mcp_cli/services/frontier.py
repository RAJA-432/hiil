from __future__ import annotations

import json
import re
from typing import Any

_FILE_PATH_RE = re.compile(
    r"(?:\b|/)((?:/[\w.-]+)+\.\w{2,5})"
)

_SENSITIVE_TOOL_PREFIXES = (
    "write", "edit", "delete", "remove", "move", "copy", "create",
    "upload", "update", "patch", "put", "add", "rename",
)


def is_sensitive_tool(name: str) -> bool:
    """Return True if the tool name matches known write/delete/edit prefixes."""
    parts = name.lower().split("_")
    return any(p.startswith(prefix) for p in parts for prefix in _SENSITIVE_TOOL_PREFIXES)


def make_file_paths_clickable(text: str) -> str:
    """Transform file paths in text into Markdown clickable links."""
    return _FILE_PATH_RE.sub(r'[\1](\1)', text)


def extract_citations(text: str, tool_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build citation entries from read-type tool results for provenance tracking."""
    citations: list[dict[str, str]] = []
    for tr in tool_results:
        if tr.get("name") in ("read_document", "read_text_resource", "search_resources"):
            result_text = tr.get("result", "")
            if not result_text or result_text.startswith("Tool error"):
                continue
            citations.append({
                "tool": tr["name"],
                "args": json.dumps(tr.get("args", {})),
                "preview": result_text[:200],
            })
    return citations



