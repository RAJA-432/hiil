from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mcp_cli.ui.renderer import MarkdownRenderer, get_renderer

RS = "\033[0m"


class ToolEventHandler:
    """Formats tool calls and their results for inline display.

    During an agent run, tools are invoked, arguments are shown, and
    results come back.  This handler produces a compact, color-coded
    one-liner for each call and optionally an expandable detail block
    for the full result.

    Usage::

        handler = ToolEventHandler()
        handler.on_call("read_file", {"path": "/foo"})
        ...
        handler.on_result("read_file", "file content here")
        # or just:
        summary = handler.format("read_file", args, result)
    """

    def __init__(self, renderer: MarkdownRenderer | None = None, expand: bool = False):
        self._renderer = renderer or get_renderer()
        self._expand = expand

        # In-flight tracking
        self._calls: dict[str, dict[str, Any]] = {}  # tool_name -> args
        self._results: dict[str, str] = {}  # tool_name -> result

    @property
    def expand(self) -> bool:
        return self._expand

    @expand.setter
    def expand(self, value: bool) -> None:
        self._expand = value

    # ── Streaming callbacks ─────────────────────────────────────────────

    def on_call(self, name: str, args: dict[str, Any]) -> None:
        """Record a tool call.  Returns nothing — the display is written
        when the result arrives."""
        self._calls[name] = args

    def on_result(
        self, name: str, result: str, print: Callable[[str], None]
    ) -> None:
        """Display one formatted line for a completed tool call."""
        line = self._format_line(name, self._calls.get(name, {}), result)
        print(line)
        self._calls.pop(name, None)
        self._results.pop(name, None)

    def on_error(self, name: str, error: str, print: Callable[[str], None]) -> None:
        """Display a failed tool call."""
        pd = self._renderer.palette_dict
        line = f"  {pd['fg_error']}X{RS} {pd['fg_code']}{name}{RS} {pd['fg_error']}{error[:200]}{RS}"
        print(line)
        self._calls.pop(name, None)

    # ── Single-shot format ──────────────────────────────────────────────

    def format(self, name: str, args: dict[str, Any], result: str) -> str:
        """Return a formatted string for a single tool call."""
        return self._format_line(name, args, result)

    # ── Internal ────────────────────────────────────────────────────────

    def _format_line(self, name: str, args: dict[str, Any], result: str) -> str:
        pd = self._renderer.palette_dict
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        icon = "OK" if not self._is_error(result) else "X"

        result_trunc = result[:80].replace("\n", " ")
        if not result_trunc:
            result_trunc = "(empty)"

        line = (
            f"  {pd['fg_warning']}{icon}{RS} "
            f"{pd['fg_code']}{name}({args_str}){RS}"
            f" {pd['fg_muted']}{result_trunc}{RS}"
        )

        if self._expand and len(result) > 80:
            details = self._format_details(name, result)
            line += f"\n{details}"

        return line

    def _format_details(self, name: str, result: str) -> str:
        pd = self._renderer.palette_dict
        try:
            parsed = json.loads(result)
            body = json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError):
            body = result[:500]

        lang = "json" if body.startswith("{") else ""
        lang_badge = f" {lang} " if lang else " result "
        header = f"{pd['bg_code']}{pd['fg_code']}{lang_badge}{RS}"
        content = f"{pd['fg_code']}{body}{RS}"
        return f"{header}\n{content}\n"

    @staticmethod
    def _is_error(result: str) -> bool:
        lower = result.lower().strip()
        return lower.startswith("error") or lower.startswith("fail") or lower.startswith("traceback")
