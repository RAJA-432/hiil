from __future__ import annotations

import json
from typing import Any

from mcp_cli.services.agents.middleware import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware

_STEP_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "mark_step_done",
        "description": (
            "Mark a playbook step as completed. Call this when you finish "
            "a step in a multi-step playbook workflow. Input the step number "
            "(1-indexed)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "step_number": {
                    "type": "integer",
                    "description": "The step number that was completed (1-indexed).",
                    "minimum": 1,
                },
                "step_name": {
                    "type": "string",
                    "description": "Optional short label for the step (e.g. 'discovery').",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes about what was done.",
                },
            },
            "required": ["step_number"],
        },
    },
}

_STATUS_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_playbook_status",
        "description": (
            "Get the current status of all steps in the active playbook. "
            "Returns which steps are done and which remain."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


@register_middleware
class TodoMiddleware(AgentMiddleware):
    """Tracks playbook step completion.

    Registers ``mark_step_done`` and ``get_playbook_status`` tools so agents
    can report progress through a multi-step playbook workflow.

    Usage in agent config::

        middleware=[TodoMiddleware(steps=6)]
    """

    def __init__(self, steps: int = 10):
        self._total_steps = max(1, steps)
        self._done: set[int] = set()
        self._notes: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        status = self._build_status()
        system_addendum = f"\n\n## Playbook Progress\n{status}"
        if messages and messages[0].get("role") == "system":
            existing = messages[0].get("content", "")
            messages[0]["content"] = existing + system_addendum
        return messages

    def get_extra_tools(self) -> list[dict[str, Any]]:
        return [_STEP_TOOL_DEFINITION, _STATUS_TOOL_DEFINITION]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        if name == "mark_step_done":
            step = args.get("step_number", 0)
            label = args.get("step_name", "")
            notes = args.get("notes", "")
            if step < 1 or step > self._total_steps:
                return True, json.dumps({
                    "error": f"Step {step} is out of range (1-{self._total_steps})",
                })
            self._done.add(step)
            if notes:
                self._notes[step] = notes
            status = self._build_status()
            msg = f"Step {step}"
            if label:
                msg += f" ({label})"
            msg += " marked done."
            return True, json.dumps({"message": msg, "status": status}, indent=2)

        if name == "get_playbook_status":
            return True, json.dumps(self._build_status(), indent=2)

        return False, None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_status(self) -> dict[str, Any]:
        steps = []
        for i in range(1, self._total_steps + 1):
            done = i in self._done
            steps.append({
                "step": i,
                "done": done,
                "notes": self._notes.get(i, ""),
            })
        return {
            "total_steps": self._total_steps,
            "completed": len(self._done),
            "remaining": self._total_steps - len(self._done),
            "steps": steps,
        }
