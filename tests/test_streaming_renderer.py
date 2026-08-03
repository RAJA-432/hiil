from __future__ import annotations

import time

from mcp_cli.ui.streaming import StreamingRenderer


class TestStreamingRenderer:
    def test_rapid_pushes_in_one_window_render_once(self, monkeypatch) -> None:
        now = 0.0
        monkeypatch.setattr(time, "monotonic", lambda: now)
        calls: list[str] = []
        renderer = StreamingRenderer(lambda t: calls.append(t) or t, throttle_ms=50)

        for _ in range(100):
            renderer.push("x")
        assert calls == []

        now += 0.05
        renderer.push("x")
        assert len(calls) == 1
        assert calls[0] == "x" * 101

    def test_flush_now_returns_full_rendered_text(self) -> None:
        renderer = StreamingRenderer(lambda t: f"<{t}>", throttle_ms=10_000)
        renderer.push("hello ")
        renderer.push("world")
        assert renderer.flush_now() == "<hello world>"

    def test_pushes_spaced_beyond_window_render_multiple_times(self, monkeypatch) -> None:
        now = 0.0
        monkeypatch.setattr(time, "monotonic", lambda: now)
        calls: list[str] = []
        renderer = StreamingRenderer(lambda t: calls.append(t) or t, throttle_ms=50)

        renderer.push("a")
        now += 0.05
        renderer.push("b")
        now += 0.05
        renderer.push("c")
        now += 0.05
        renderer.push("d")

        assert calls == ["ab", "c", "d"]

    def test_on_output_receives_rendered_text(self) -> None:
        out: list[str] = []
        renderer = StreamingRenderer(lambda t: t.upper(), on_output=out.append, throttle_ms=10_000)
        renderer.push("hi")
        renderer.flush_now()
        assert out == ["HI"]

    def test_flush_now_empty_when_nothing_pending(self) -> None:
        renderer = StreamingRenderer(lambda t: t, throttle_ms=10_000)
        assert renderer.flush_now() == ""
