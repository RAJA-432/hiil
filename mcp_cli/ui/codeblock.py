from __future__ import annotations

import re
from collections.abc import Callable

from mcp_cli.ui.renderer import MarkdownRenderer, get_renderer

RS = "\033[0m"

_FENCE = re.compile(r"^(?P<fence>`{3,}|~{3,})\s*(?P<lang>\w*)\s*$")


class CodeBlockAccumulator:
    """Accumulates streaming fenced code blocks and renders them as a whole.

    During streaming, code blocks arrive token by token.  Rendering an
    incomplete code block (missing the closing fence) looks bad and messes
    up the terminal.  This buffer intercepts lines that belong to a fenced
    code block and only flushes them to the output callback when the block
    is complete.

    Usage::

        acc = CodeBlockAccumulator()
        for chunk in stream:
            acc.feed(chunk, on_text=lambda t: print(t, end=""))

    If a code block remains unclosed after the stream ends, call
    ``flush(…)`` to render it anyway.
    """

    def __init__(self, renderer: MarkdownRenderer | None = None):
        self._renderer = renderer or get_renderer()

        # current code block state
        self._in_block = False
        self._fence_char = ""
        self._fence_len = 0
        self._lang = ""
        self._lines: list[str] = []
        self._buf = ""

    @property
    def in_block(self) -> bool:
        return self._in_block

    def feed(self, text: str, on_text: Callable[[str], None]) -> None:
        """Process incoming text, buffering code block content.

        Text outside code blocks is forwarded to ``on_text`` immediately.
        Code block content is buffered and flushed when the closing fence
        arrives.
        """
        self._buf += text

        while "\n" in self._buf:
            idx = self._buf.index("\n")
            line = self._buf[: idx + 1]
            self._buf = self._buf[idx + 1 :]
            self._feed_line(line, on_text)

    def flush(self, on_text: Callable[[str], None]) -> None:
        """Flush any remaining buffered content.

        Call this at the end of a stream to ensure any unclosed code block
        is rendered even without a closing fence.
        """
        if self._in_block and self._lines:
            rem = self._buf
            if rem:
                self._lines.append(rem)
                self._buf = ""
            # no closing fence — render what we have
            on_text(self._render_block(self._lang, self._lines))
            self._reset()
        elif self._buf:
            on_text(self._buf)
            self._buf = ""

    # ── Internal ────────────────────────────────────────────────────────

    def _feed_line(self, line: str, on_text: Callable[[str], None]) -> None:
        m = _FENCE.match(line.strip())
        if m:
            fence = m.group("fence")
            lang = m.group("lang")

            if not self._in_block:
                self._in_block = True
                self._fence_char = fence[0]
                self._fence_len = len(fence)
                self._lang = lang
                self._lines = []
            else:
                # closing fence — render the block
                on_text(self._render_block(self._lang, self._lines))
                self._reset()
            return

        if self._in_block:
            self._lines.append(line)
        else:
            on_text(line)

    def _render_block(self, lang: str, lines: list[str]) -> str:
        # The MarkdownRenderer already handles the box-drawing and palette
        # logic for fenced blocks. We just need to pass it the raw code.
        code = "".join(lines).rstrip("\n")

        # We mimic a markdown fence so MarkdownRenderer._render_fenced_blocks can handle it,
        # or we call _render_code_block directly.
        # Since _render_code_block is "private" in renderer.py, we'll use the render method
        # by wrapping it in fences, or we can make _render_code_block public.
        # Given the current architecture, wrapping in fences is the cleanest way to
        # reuse the Renderer's polished logic.

        fence = "```"
        lang_part = lang if lang else ""
        wrapped = f"{fence}{lang_part}\n{code}\n{fence}"

        rendered = self._renderer.render(wrapped)

        # Add the [copy] shortcut at the end as requested in the design
        pd = self._renderer.palette_dict
        footer = f"\n  {pd['fg_muted']}shortcut: [copy]{RS}"
        return f"{rendered}{footer}\n"

    def _reset(self) -> None:
        self._in_block = False
        self._fence_char = ""
        self._fence_len = 0
        self._lang = ""
        self._lines = []
