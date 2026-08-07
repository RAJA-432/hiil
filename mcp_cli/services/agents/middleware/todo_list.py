from __future__ import annotations

import json
from typing import Any

from mcp_cli.services.agents.middleware.base import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware

_VALID_STATUSES = ("pending", "in_progress", "completed")

_WRITE_TODOS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "write_todos",
        "description": (
            "Write out the agent's full to-do list for the current task. "
            "Each item has an id (1-based integer), a title, and a status: "
            "pending (not started), in_progress (being worked on now), or "
            "completed (done). Calling this replaces the entire list. Use it "
            "at the start of a multi-step task to plan, and update item "
            "statuses as you work."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": list(_VALID_STATUSES),
                            },
                        },
                        "required": ["id", "title", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    },
}


@register_middleware
class TodoListMiddleware(AgentMiddleware):
    """Tracks a general-purpose planning to-do list.

    Registers the ``write_todos`` and ``get_todos`` tools so agents can plan
    a multi-step task up front and tick items off as they make progress.

    Usage in agent config::

        middleware=[TodoListMiddleware(max_items=20)]
    """

    def __init__(self, max_items: int = 20):
        self._max_items = max_items
        self._todos: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Middleware API
    # ------------------------------------------------------------------

    def before_run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._todos:
            return messages
        plan = json.dumps(self._todos, indent=2)
        system_addendum = f"\n\n## Task Plan\n{plan}"
        if messages and messages[0].get("role") == "system":
            existing = messages[0].get("content", "")
            messages[0]["content"] = existing + system_addendum
        else:
            messages = [{"role": "system", "content": system_addendum}] + messages
        return messages

    def get_extra_tools(self) -> list[dict[str, Any]]:
        return [_WRITE_TODOS_DEFINITION]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        if name == "write_todos":
            raw = args.get("todos")
            if not isinstance(raw, list):
                return True, json.dumps({"error": "todos must be a list"})
            normalized = self._normalize(raw)
            note = None
            if len(normalized) > self._max_items:
                normalized = normalized[: self._max_items]
                note = f"List truncated to {self._max_items} items"
            self._todos = normalized
            result = {"ok": True, "count": len(normalized), "todos": self._todos}
            if note:
                result["note"] = note
            return True, json.dumps(result, indent=2)

        if name == "get_todos":
            return True, json.dumps({"todos": self._todos}, indent=2)

        return False, None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def update_status(self, todo_id: int, status: str) -> bool:
        """Update a todo item's status. Returns True if the item was found."""
        if status not in _VALID_STATUSES:
            return False
        for item in self._todos:
            if item.get("id") == todo_id:
                item["status"] = status
                return True
        return False

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a copy of the current to-do list."""
        return [dict(item) for item in self._todos]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _normalize(self, raw: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            try:
                todo_id = int(item.get("id", idx + 1))
            except (TypeError, ValueError):
                todo_id = idx + 1
            title = item.get("title", "")
            if not isinstance(title, str):
                title = str(title)
            status = item.get("status", "pending")
            if status not in _VALID_STATUSES:
                status = "pending"
            normalized.append({"id": todo_id, "title": title, "status": status})
        return normalized
