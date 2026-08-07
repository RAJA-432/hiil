from __future__ import annotations

import json
import re
from typing import Any

_FILE_PATH_RE = re.compile(
    r"(?:\b|/)((?:/[\w.-]+)+\.\w{2,5})"
)

_SENSITIVE_TOOL_PREFIXES = frozenset({
    "write", "edit", "delete", "remove", "move", "copy", "create",
    "upload", "update", "patch", "rename", "overwrite",
})

_SENSITIVE_TOOL_WORDS = frozenset({
    "shell", "bash", "sh", "zsh", "powershell", "cmd",
    "exec", "execute", "system", "sudo",
    "rm", "rmdir", "del", "unlink", "kill",
    "shutdown", "reboot", "wipe", "format", "truncate", "mkfs", "dd",
    "chmod", "chown",
})

_TOOL_NAME_SEPARATOR_RE = re.compile(r"[\s_\-./]+")


def is_sensitive_tool(name: str) -> bool:
    """Return True if the tool name is a shell/exec or destructive write operation."""
    segments = _TOOL_NAME_SEPARATOR_RE.split(name.lower())
    return any(
        seg in _SENSITIVE_TOOL_WORDS or seg in _SENSITIVE_TOOL_PREFIXES
        for seg in segments
    )


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



