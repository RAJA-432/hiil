"""Pre-write discovery guard for the agent tool loop.

Tracks the resources an agent actually observed this session (via the
read/glob/grep/list tools) and flags guarded write tools that target an
unobserved resource.  Three modes: ``off`` (no-op), ``warn`` (allow but
annotate the result) and ``block`` (short-circuit with a ``[discovery]``
result so the client tool call is never made).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_VALID_MODES = {"off", "warn", "block"}

_DISCOVERY_PATH_TOOLS = {
    "read_text_resource": "path",
    "read_text_batch": "path",
    "read_dir": "path",
}

_DISCOVERY_KEY_TOOLS = {
    "read_document": "doc_id",
    "glob": "pattern",
    "grep": "pattern",
    "search_resources": "query",
}

_GUARDED_PATH_TOOLS = {
    "write_file": "path",
    "edit_file": "path",
    "delete_file": "path",
    "move_file": "path",
    "copy_file": "path",
    "create_directory": "path",
    "mkdir": "path",
    "rmdir": "path",
}

_GUARDED_KEY_TOOLS = {
    "edit_document": "doc_id",
    "save_draft": "to",
    "send_draft": "to",
}


def _canonicalize_path(value: str) -> str:
    resolved = Path(value).expanduser().resolve(strict=False).as_posix()
    if os.name == "nt":
        resolved = resolved.lower()
    return resolved


class DiscoveryTracker:
    """Records observed resources and guards writes to unobserved targets."""

    def __init__(self, mode: str = "off") -> None:
        if mode not in _VALID_MODES:
            raise ValueError(f"discovery mode must be one of {sorted(_VALID_MODES)}, got {mode!r}")
        self.mode = mode
        self.observed: set[str] = set()

    def record(self, tool_name: str, args: dict[str, Any]) -> None:
        if self.mode == "off":
            return
        key = _DISCOVERY_PATH_TOOLS.get(tool_name) or _DISCOVERY_KEY_TOOLS.get(tool_name)
        if key is None:
            return
        raw = args.get(key)
        if not isinstance(raw, str) or not raw:
            return
        self.observed.add(self._normalize(tool_name, raw))

    def check(self, tool_name: str, args: dict[str, Any]) -> str | None:
        if self.mode == "off":
            return None
        key = _GUARDED_PATH_TOOLS.get(tool_name) or _GUARDED_KEY_TOOLS.get(tool_name)
        if key is None:
            return None
        raw = args.get(key)
        if not isinstance(raw, str) or not raw:
            return None
        if self._normalize(tool_name, raw) in self.observed:
            return None
        return (
            f"[discovery] Tool '{tool_name}' targets '{raw}', which was not observed "
            "this session (read/glob/grep/list it first)"
        )

    @staticmethod
    def _normalize(tool_name: str, raw: str) -> str:
        if tool_name in _DISCOVERY_PATH_TOOLS or tool_name in _GUARDED_PATH_TOOLS:
            return _canonicalize_path(raw)
        return raw
