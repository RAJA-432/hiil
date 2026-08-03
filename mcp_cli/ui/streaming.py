from __future__ import annotations

import time
from collections.abc import Callable


class StreamingRenderer:
    """Throttled inline renderer for streaming markdown text.

    Incoming tokens are buffered and passed through the wrapped render
    function at most once per ``_THROTTLE_MS`` window instead of once per
    token, so a burst of N pushes coalesces into a single render call.
    """

    _THROTTLE_MS = 50

    def __init__(
        self,
        render_fn: Callable[[str], str],
        on_output: Callable[[str], None] | None = None,
        throttle_ms: int = _THROTTLE_MS,
    ) -> None:
        self._render_fn = render_fn
        self._on_output = on_output
        self._throttle = throttle_ms / 1000.0
        self._buf = ""
        self._last_render = time.monotonic()

    def push(self, chunk: str) -> None:
        """Buffer a chunk and flush it if the throttle window has elapsed."""
        self._buf += chunk
        if time.monotonic() - self._last_render >= self._throttle:
            self._emit()

    def emit_raw(self, text: str) -> None:
        """Emit pre-rendered output (e.g. a completed code block) immediately."""
        self.flush_now()
        if self._on_output:
            self._on_output(text)

    def flush_now(self) -> str:
        """Force a synchronous render of the buffered text and return it."""
        return self._emit()

    def _emit(self) -> str:
        if not self._buf:
            return ""
        rendered = self._render_fn(self._buf)
        self._buf = ""
        self._last_render = time.monotonic()
        if self._on_output:
            self._on_output(rendered)
        return rendered
