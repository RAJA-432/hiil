from __future__ import annotations

import datetime
import json
import os


async def handle_agent_cmd(chat, subcmd: str, rest: str, prompt_async) -> str:
    """Handle /agent subcommands (create, list, search, pause, approve, reject)."""
    safe_base = os.path.abspath(".claude")
    for val in [subcmd, rest]:
        candidate = os.path.abspath(os.path.join(safe_base, val))
        if os.path.commonpath([candidate, safe_base]) != safe_base:
            return "Security violation: Directory traversal not allowed."

    if subcmd == "create":
        if not rest:
            return "Usage: /agent create <agent_name>"
        agent_name = rest.strip()
        base_agent_dir = os.path.join(".claude", "agents")
        if os.path.exists(os.path.join(base_agent_dir, f"agent_{agent_name}")):
            return f"Agent '{agent_name}' already exists."
        agent_dir = os.path.join(base_agent_dir, f"agent_{agent_name}")
        os.makedirs(agent_dir, exist_ok=True)
        with open(os.path.join(agent_dir, "plan.json"), "w", encoding="utf-8") as f:
            json.dump([], f)
        with open(os.path.join(agent_dir, "output.log"), "w", encoding="utf-8") as f:
            f.write("")
        os.makedirs(os.path.join(agent_dir, "interrupted"), exist_ok=True)
        return f"Agent '{agent_name}' created successfully!"

    elif subcmd == "list":
        base_agent_dir = os.path.join(".claude", "agents")
        if not os.path.exists(base_agent_dir):
            return "No agents installed yet."
        agents = [
            d.replace("agent_", "")
            for d in os.listdir(base_agent_dir)
            if os.path.isdir(os.path.join(base_agent_dir, d)) and d.startswith("agent_")
        ]
        if not agents:
            return "No agents found."
        return f"Available agents: {', '.join(agents)}"

    elif subcmd == "search":
        if not rest:
            return "Usage: /agent search <agent_name> <query>"
        token = rest.strip().split(maxsplit=1)
        if len(token) != 2:
            return "Usage: /agent search <agent_name> <query>"
        agent_name, query = token[0], token[1]
        agent_path = os.path.join(".claude", "agents", f"agent_{agent_name}", "output.log")
        if not os.path.isfile(agent_path):
            return f"Agent '{agent_name}' has no output.log yet."
        matches = []
        with open(agent_path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if query.lower() in line.lower():
                    matches.append(f"{i}: {line.rstrip()}")
        if not matches:
            return f"No matches for '{query}' in '{agent_name}'."
        return "\n".join(matches)

    elif subcmd == "pause":
        if not rest:
            return "Usage: /agent pause <agent_name>"
        agent_name = rest.strip()
        agent_path = os.path.join(".claude", "agents", f"agent_{agent_name}")
        pause_flag = os.path.join(agent_path, "interrupted", "paused.flag")
        try:
            if not os.path.exists(agent_path):
                return f"Agent '{agent_name}' does not exist."
            confirmation = await prompt_async(f"Pause agent '{agent_name}'? (y/n): ")
            if confirmation.strip().lower() not in ("y", "yes"):
                return "Pause cancelled by user."
            with open(pause_flag, "w", encoding="utf-8") as f:
                f.write(f"Paused at {datetime.datetime.now().isoformat()}")
            return f"Agent '{agent_name}' successfully paused. Awaiting approval."
        except Exception:
            return f"Error while pausing agent '{agent_name}'"

    elif subcmd == "approve":
        if not rest:
            return "Usage: /agent approve <agent_name>"
        agent_name = rest.strip()
        agent_path = os.path.join(".claude", "agents", f"agent_{agent_name}")
        paused_flag = os.path.join(agent_path, "interrupted", "paused.flag")
        try:
            if not os.path.exists(agent_path):
                return f"Agent '{agent_name}' does not exist."
            if not os.path.isfile(paused_flag):
                return f"Agent '{agent_name}' is not paused."
            confirmation = await prompt_async(f"Approve and resume agent '{agent_name}'? (y/n): ")
            if confirmation.strip().lower() not in ("y", "yes"):
                return "Approval cancelled by user."
            os.remove(paused_flag)
            return f"Agent '{agent_name}' approved and resumed."
        except Exception as exc:
            return f"Error while approving agent '{agent_name}': {str(exc)}"

    elif subcmd == "reject":
        if not rest:
            return "Usage: /agent reject <agent_name>"
        agent_name = rest.strip()
        agent_path = os.path.join(".claude", "agents", f"agent_{agent_name}")
        paused_flag = os.path.join(agent_path, "interrupted", "paused.flag")
        try:
            if not os.path.exists(agent_path):
                return f"Agent '{agent_name}' does not exist."
            if not os.path.isfile(paused_flag):
                return f"Agent '{agent_name}' is not paused."
            reason = await prompt_async(f"Reason for rejecting agent '{agent_name}': ")
            if not reason.strip():
                reason = "No reason provided"
            confirmation = await prompt_async(f"Reject agent '{agent_name}'? (y/n): ")
            if confirmation.strip().lower() not in ("y", "yes"):
                return "Rejection cancelled by user."
            os.remove(paused_flag)
            return f"Agent '{agent_name}' rejected. Reason logged."
        except Exception as exc:
            return f"Error while rejecting agent '{agent_name}': {str(exc)}"

    else:
        return f"Unknown agent sub-command: {subcmd}."
