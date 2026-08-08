from __future__ import annotations

import json
import re
from typing import Any

from mcp_cli.services.agents.permissions import PermissionEnforcer
from mcp_cli.services.logging import get_logger

logger = get_logger("agent_tool_gate")


class GateKeeper:
    """Parses tool arguments and enforces filesystem permissions before dispatch."""

    def __init__(self, agent_id: str, perm_enforcer: PermissionEnforcer | None) -> None:
        self.agent_id = agent_id
        self._perm_enforcer = perm_enforcer

    def _parse_args(self, call: Any, name: str) -> tuple[dict[str, Any] | None, str | None]:
        """Parse tool arguments, recovering from common malformed-JSON wrapping."""
        try:
            return json.loads(call.function.arguments or "{}"), None
        except json.JSONDecodeError:
            # If the AI produces malformed JSON, try to recover by stripping
            # potential markdown formatting or trailing characters.
            raw_args = call.function.arguments or "{}"
            try:
                # Common issue: AI wraps JSON in ```json ... ```
                if "```" in raw_args:
                    raw_args = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", raw_args).strip()
                return json.loads(raw_args), None
            except Exception as exc:
                logger.warning("Agent %s: Malformed tool arguments for %s. %s. Raw: %s",
                               self.agent_id, name, exc, raw_args)
                return None, (
                    f"[invalid-args] Failed to parse arguments for '{name}': {exc}\n"
                    f"Raw input received: {raw_args[:500]}\n"
                    f"Please provide valid JSON arguments for this tool and retry."
                )

    def _perm_gate(self, name: str, args: dict[str, Any]) -> str | None:
        """Check filesystem permissions before executing."""
        if not self._perm_enforcer:
            return None
        return self._perm_enforcer.inspect_tool_args(name, args)
