---
name: claified-agent-cli-design
description: Design document for a user‑friendly, ethical CLI to manage LangGraph agents (search, edit, approve, & respond)
metadata:
  type: project
  author: Claude AI
  date: 2026-07-21
---

# 🎯 Project Goal
We will create a **Command‑Line Interface** that lets users *create*, *observe*, *pause*, *approve*, or *reject* the actions of LangGraph agents in a simple, transparent, and ethically–aligned way. The CLI will *not* expose private data or sensitive logic to the user and will provide clear prompts and logs.

# ⚙️ Core Capabilities
| Action | What it does | Where it fits | Notes |
|--------|--------------|--------------|-------|
| `agent create [name]` | Scaffold a new agent with a standard set of tools (Grep, Bash, WebFetch, etc.) | Agent Lifecycle | Prompts for a short description; records user intent |
| `agent list` | Display running agents, their status, and recent logs | Observation | Uses a dedicated `summary.log` to hide raw logs |
| `agent search [query]` | Query files or web, returning a short preview | Data retrieval | Uses safe defaults (no deep recursion; deny non‑ASCII paths) |
| `agent pause [id]` | Suspend the agent at the next ready point | Workflow control | Pauses are logged, no immutable state changes |
| `agent approve [id]` | Resume a paused task after user confirmation | Approval workflow | Requires explicit confirmation (`Yes/No`) |
| `agent reject [id]` | Cancel a paused task | Rejection workflow | Locks the cursor on the task; logs the reason |
| `agent respond [id]` | Let the user edit the agent’s draft response | Post‑process | Provides an interactive editor in the terminal |

# 📁 File Organization
```
.claude/agents/
├─ agent_name-
│   ├─ plan.json          # Current task queue (JSON)
│   ├─ output.log         # Plain‑text stdout & stderr history
│   ├─ interrupted/       # Snapshot archives of paused runs
│   │   └─ <id>.json      # JSON of the paused state
├ hlut
├─ annotations.md   # audit trail of decisions
```

All files are written/read in UTF‑8 and are *never* auto‑overwritten without user confirmation.

# 📌 Security & Ethics
1. **GDPR‑friendly** – No personalkunden data is stored beyond the agent’s memory unless explicitly requested by the user.
2. **Explicit Opt‑in** – All pauses require a user‑prompt; no background writes that could leak secrets.
3. **State Snapshots** – Paused states are stored only locally, giving the user full control of deletion.
4. **Audit Log** – `annotations.md` contains timestamped entries: ``[2026‑07‑21 14:32] User approved interrupt X for agent A``.

# 🧪 Testing & Validation
- Unit test: creating an agent, listing, pausing, approving, editing the output.
- Mock a LangGraph agent that performs an HTTP request; ensure no real network calls unless `--allow-net` is specified.
- Test concurrent agents: confirm they run in isolated worktrees.

# 🚀 Next Steps
1. Create the AVL directory skeleton.
2. Write the CLI helper that normalizes commands and calls MCP APIs.
3. Add a `--verbose` flag for debugging.

---
> **Note**: All code changes will be added through the commit workflow defined in your repository (use `git commit -m "…"`).
