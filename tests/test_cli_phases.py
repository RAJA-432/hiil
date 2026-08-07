from __future__ import annotations

from typing import Any

from mcp_cli.ui.app import CliApp


def _app() -> CliApp:
    return CliApp(chat=object())


class TestRenderPhases:
    def test_empty_phases_returns_empty(self) -> None:
        assert _app()._render_phases([]) == []

    def test_single_state_event_formatted(self) -> None:
        lines = _app()._render_phases(
            [{"type": "state", "agent_id": "agent_x", "phase": "EXECUTING"}]
        )
        assert len(lines) == 1
        assert "agent_x" in lines[0]
        assert "EXECUTING" in lines[0]

    def test_multiple_events_keep_order(self) -> None:
        events: list[dict[str, Any]] = [
            {"type": "state", "agent_id": "agent_x", "phase": "THINKING"},
            {"type": "state", "agent_id": "agent_x", "phase": "DELEGATING"},
            {"type": "state", "agent_id": "agent_y", "phase": "REPORTING"},
            {"type": "state", "agent_id": "agent_y", "phase": "DONE"},
        ]
        lines = _app()._render_phases(events)
        assert len(lines) == 4
        joined = "".join(lines)
        assert joined.index("THINKING") < joined.index("DELEGATING") < joined.index("REPORTING") < joined.index("DONE")
        assert joined.index("[agent_x]") < joined.index("[agent_y]")

    def test_missing_keys_use_defaults(self) -> None:
        lines = _app()._render_phases([{"type": "state"}])
        assert len(lines) == 1
        assert "?" in lines[0]
        assert "UNKNOWN" in lines[0]
