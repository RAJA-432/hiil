from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Any

from mcp_cli.ui.renderer import MarkdownRenderer, get_renderer

RS = "\033[0m"

# ── Role badge maps ─────────────────────────────────────────────────────

BADGES: dict[str, str] = {
    "user": "You",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}

# Color keys from the theme system (we reference by name; the renderer
# resolves them from its palette).
ROLE_COLORS: dict[str, str] = {
    "user": "fg_primary",
    "assistant": "fg_secondary",
    "system": "fg_muted",
    "tool": "fg_warning",
}

SEP_LEN = 60


class MessageManager:
    """Formats message blocks with role headers, separators, and timestamps.

    Produces ANSI-escaped strings ready for ``print()``.
    """

    def __init__(self, renderer: MarkdownRenderer | None = None):
        self._renderer = renderer or get_renderer()
        self._compact = False
        self._show_timestamps = False

    # ── Config ──────────────────────────────────────────────────────────

    @property
    def compact(self) -> bool:
        return self._compact

    @compact.setter
    def compact(self, value: bool) -> None:
        self._compact = value

    @property
    def show_timestamps(self) -> bool:
        return self._show_timestamps

    @show_timestamps.setter
    def show_timestamps(self, value: bool) -> None:
        self._show_timestamps = value

    # ── Public formatting API ───────────────────────────────────────────

    def user_header(self, name: str = "You") -> str:
        """Returns the ``[name]`` badge with primary color."""
        return self._badge(name, "fg_primary")

    def assistant_header(self, name: str = "Assistant") -> str:
        """Returns the ``[name]`` badge with secondary color."""
        return self._badge(name, "fg_secondary")

    def user_separator(self, text_width: int) -> str:
        """Muted horizontal bar under the user message."""
        w = min(max(text_width, 4), SEP_LEN)
        bar = "-" * w
        return f"  {self._style('border')}{bar}{RS}"

    def assistant_separator(self) -> str:
        """Full-width closing bar after the assistant response."""
        bar = "-" * SEP_LEN
        return f"{self._style('border')}{bar}{RS}"

    def format_user_block(self, text: str, user_name: str = "You", timestamp: str = "") -> str:
        """Complete user message block with header, text, and bar."""
        pd = self._renderer.palette_dict
        ts = self._fmt_ts(timestamp)
        header = f"{self._badge(user_name, 'fg_primary')}{ts}"
        rendered = self._renderer.render(text)
        sep = self.user_separator(len(text))
        return f"\n{header}\n  {pd['fg']}{rendered}{RS}\n  {sep}"

    def format_assistant_block(self, text: str, timestamp: str = "") -> str:
        """Complete assistant message block with header, text, and closing bar."""
        pd = self._renderer.palette_dict
        ts = self._fmt_ts(timestamp)
        header = f"{self._badge('Assistant', 'fg_secondary')}{ts}"
        rendered = self._renderer.render(text)
        sep = self.assistant_separator()
        return f"\n{header}\n  {pd['fg']}{rendered}{RS}\n{sep}"

    def format_tool_call(self, name: str, args: dict[str, Any], result: str) -> str:
        """Inline tool call display with improved styling and result truncation.

        Returns a formatted string for the tool call, highlighting errors and
        truncating results to 4 lines.
        """
        pd = self._renderer.palette_dict
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())

        # Truncate result to 4 lines
        result_lines = result.splitlines()
        if len(result_lines) > 4:
            truncated_result = "\n".join(result_lines[:4]) + f"\n  {pd['fg_muted']}... (use /expand to see more){RS}"
        else:
            truncated_result = result

        is_error = "error" in result.lower() or "exception" in result.lower()
        icon = f"{pd['fg_error']}⚠ ERROR{RS}" if is_error else f"{pd['fg_success']}✔{RS}"

        # Tool call layout
        return (
            f"\n  {icon} {pd['fg_code']}{name}({args_str}){RS}\n"
            f"  {pd['fg_muted']}{truncated_result}{RS}"
        )

    # ── Internal helpers ────────────────────────────────────────────────

    def _badge(self, text: str, color_key: str) -> str:
        pd = self._renderer.palette_dict
        label = f" 👤 {text} " if "You" in text else f" 🤖 {text} " if "Assistant" in text else f" {text} "
        return f"{pd['bg']}{pd[color_key]}{label}{RS}"

    def _style(self, key: str) -> str:
        return self._renderer.palette(key)

    def _fmt_ts(self, ts: str) -> str:
        if not self._show_timestamps or not ts:
            return ""
        try:
            dt = datetime.fromisoformat(ts)
            return f" {self._style('fg_muted')}[{dt.strftime('%H:%M:%S')}]{RS}"
        except Exception:
            return ""


# ── SpinnerManager ──────────────────────────────────────────────────────

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_DOT = "..."

_STATUS_LABELS: dict[str, str] = {
    "thinking": "thinking",
    "streaming": "streaming",
    "tool": "tool call",
}


class SpinnerManager:
    """Manages an inline spinner/status line while waiting for streaming output.

    Usage::

        spinner = SpinnerManager()
        spinner.start("thinking")
        # ... first token arrives ...
        spinner.clear()
        # ... stream content ...
    """

    def __init__(self, renderer: MarkdownRenderer | None = None):
        self._renderer = renderer or get_renderer()
        self._task: asyncio.Task | None = None
        self._active = False
        self._status = "thinking"

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        self._status = value
        if self._active:
            self._redraw()

    def _redraw(self) -> None:
        """Redraw the spinner line with the current status label."""
        label = _STATUS_LABELS.get(self._status, self._status)
        pd = self._renderer.palette_dict
        frame = _SPINNER_FRAMES[0]
        sys.stdout.write(f"\r  {pd['fg_muted']}{frame} {label}{RS}\033[K")
        sys.stdout.flush()

    async def spin(self, status: str = "thinking") -> None:
        """Run the spinner in the background (call via ``asyncio.create_task``)."""
        self._active = True
        self._status = status
        label = _STATUS_LABELS.get(status, status)
        pd = self._renderer.palette_dict
        try:
            i = 0
            while self._active:
                frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
                sys.stdout.write(
                    f"\r  {pd['fg_muted']}{frame} {label}{RS}"
                )
                sys.stdout.flush()
                await asyncio.sleep(0.1)
                i += 1
        except asyncio.CancelledError:
            pass
        finally:
            self._clear_line()

    def start(self, status: str = "thinking") -> None:
        """Launch the spinner in a background task."""
        self.stop()
        self._task = asyncio.create_task(self.spin(status))

    def stop(self) -> None:
        """Stop the spinner and clear its line."""
        self._active = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._clear_line()

    def clear(self) -> None:
        """Clear the spinner line (keeps spinner stopped)."""
        self._active = False
        self._clear_line()

    @staticmethod
    def _clear_line() -> None:
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
