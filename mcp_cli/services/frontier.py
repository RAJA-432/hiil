from __future__ import annotations

import asyncio
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


class ApprovalManager:
    def __init__(self):
        """Set up an async approval gate for sensitive tool calls."""
        self._pending: dict[str, Any] | None = None
        self._event = asyncio.Event()
        self._result = False
        self._lock = asyncio.Lock()

    @property
    def pending(self) -> dict[str, Any] | None:
        """Return the pending approval request, or None if none is pending."""
        return self._pending

    async def request(self, tool_name: str, args: dict[str, Any]) -> bool:
        """Wait for a user to approve or deny a sensitive tool call and return the result."""
        async with self._lock:
            self._pending = {"name": tool_name, "args": args}
            self._event.clear()
            self._result = False
        await self._event.wait()
        async with self._lock:
            self._pending = None
            return self._result

    def resolve(self, approved: bool) -> None:
        """Resolve the pending approval with the given boolean decision."""
        self._result = approved
        self._pending = None
        self._event.set()

    def reset(self) -> None:
        """Clear any pending approval and unblock waiters."""
        self._pending = None
        self._event.set()
