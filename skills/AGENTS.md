# AGENTS.md — Operating Manual

## Conventions

- All monetary values in USD, 2 decimal places.
- Quote line items: quantity × unit_price = line_total. No LLM-guessed math.
- Volume discount thresholds: >$10,000 → 5%; >$50,000 → 10%; >$100,000 → 15%.
- Approval required before: (a) saving a mail draft, (b) adding a new customer.
- Use `/skills/playbooks/<task>.md` for step-by-step workflows.
- Mark steps complete with `mark_step_done(step_number)` after finishing each step.
- Read this file and the relevant playbook at the start of every task.

## Subagents

| Agent | Role | Tools | Memory Files |
|-------|------|-------|-------------|
| **chinook-analyst** | Database analyst — run SQL queries against the Chinook database | `read_query`, `list_tables`, `describe_table` | AGENTS.md, playbooks |
| **inbox-manager** | Mail manager — triage inbox, compose and save drafts | `list_messages`, `get_message`, `send_draft` (gated), `save_draft` (gated) | AGENTS.md, playbooks |
| **quote-reviewer** | Quote sanity checker — verify line-item math, discount %, and grand total | `read_file`, `calculate_quote` (read-only check), `search_files` | AGENTS.md, rfq-quote.md |
| **genre-researcher** | Newsletter researcher — gather and summarize content for one genre | `web_search`, `web_fetch`, `summarize` | AGENTS.md, newsletter.md |
| **media-designer** | Media & design assistant — generate images and find stock templates | `graphic_art` (gated), `search_template_images`, `search_template_videos` | AGENTS.md |
| **travel-agent** | Travel planner — resolve airports and search mock flights | `search_airports`, `search_flights` | AGENTS.md |
| **health-advisor** | Health info assistant — curated educational health lookup | `search_healthcare` | AGENTS.md |
| **history-librarian** | Browsing-history researcher — search and record local history | `browser_search`, `browser_add` (gated) | AGENTS.md |

## Orchestration Rules

- The main agent reads the relevant playbook, then spawns subagents as needed.
- **Sequential** subagents: run one after another when order matters (e.g., discovery → pricing → review).
- **Parallel** subagents: fan out when independent (e.g., one genre-researcher per newsletter section). Stitch results after all complete.
- When a subagent returns `status=waiting`, present the pending_interrupt to the user for approval, then call resume() with the decision.

---

## Session Log — Drishti Engine Integration (2026-08-07)

### Completed this session
- **Refactor (God-module decomposition via 5 subagents)** — behavior-preserving:
  - `mcp_cli/services/chat.py` → split into `session/turn_pipeline.py`, `session/recovery.py`, `session/session_manager.py`, `session/image_input.py`; `CliChat` is now a thin facade.
  - `mcp_cli/services/agents/runner.py` → `tool_gate.py` (GateKeeper), `agent_tools.py`, `memory_provider.py`.
  - `vajra_gate/services/reward.py` → package: `events`, `feedback`, `response`, `tools`, `session`, `errors`, `engine`, `store` + facade `__init__`.
  - `mcp_cli/ui/app.py` → `turn_renderer.py` + `commands/{help,status,history_cmds}.py`; Ctrl+C handling fixed.
  - `mcp_cli/services/claude.py` + `veda_engine/tools/shell.py` → `normalizer.py` + `shell_safety.py`.
  - **Verification:** full suite identical pre-existing 20 failures (confirmed by stash baseline); ruff clean; mypy 11→8 (2 fixed by refactor).
- **INR display** — `usage.py`: `INR_PER_USD` (env `HIIL_INR_PER_USD`, default 86) + `format_cost()`; `/usage` + turn delta now print ₹. (cost still stored in USD)
- **Drishti Engine** — package complete: 8 tools (media, flights, healthcare, browser history), 27 tests passing; registered in `config.yaml` (`drishti` server), `pyproject.toml` packages, `SUBAGENT_REGISTRY` (media-designer, travel-agent, health-advisor, history-librarian), `README.md`, `SKILL.md`; CI/Makefile lint+typecheck scopes updated.
- **ToolRegistry wiring** — added EXPERT categories `media`/`travel`/`health`/`history` + keyword routing for drishti tools.
- **Classifier tests** — added 7 rule-based routing tests for the 4 new subagents (all passing).

### Verified green
- `ruff check` clean on all refactored + new files.
- `pytest tests/test_route_classifier.py::TestRuleBased` → 17 passed.
- `pytest tests/test_drishti_*` (27), agent tests (48 passed).

### Pre-existing failures (DO NOT fix unless assigned — owned by other phases)
The 20 failing tests all arise from test fixtures that build `CliChat` via `object.__new__` without setting `tool_runner` (first failure) and/or `registry` on the constructed object. Those attributes are required by `turn_pipeline.TurnPipeline` at runtime (`chat.py:508` uses `self.tool_runner`, `chat.py:509` uses `self.registry`). This is a pre-existing **Gap 3** issue unrelated to the MCP server split. Fixes involve adding the missing fixture setup.

- `tests/test_route_classifier.py::TestDispatchWiring` (2 failures) – fixtures do not set either attribute
- `tests/test_agent_lifecycle.py` (3 failures) – fixtures set `tool_runner` but not `registry`
- `tests/test_chat_pipeline.py` (10 failures) – fixtures do not set either attribute (actual count is 10, not 11)
- `tests/test_vision_pipeline.py::TestSendImageBranching` (5 failures) – fixtures do not set either attribute

### TODO next session (drishti integration, remaining gaps)
1. **Gap 3 — fix fixture `CliChat` setup** in `tests/test_route_classifier.py`, `tests/test_agent_lifecycle.py`, `tests/test_chat_pipeline.py`, `tests/test_vision_pipeline.py`: for each `_make_chat`/fixture, add both `chat.tool_runner = _FakeToolRunnerChat()` and `chat.registry = ToolRegistry()` (or equivalent minimal stubs). This unblocks the whole dispatch + verification + vision test suites (currently 20 red).
2. **Gap 4 — document drishti tools in `/help`**: add a drishti tools entry to `mcp_cli/ui/commands/help.py` `HELP_SECTIONS`.
3. **Add a `ToolRegistry` test** (`tests/test_registry.py`) asserting `resolve_tools` selects drishti pools for flight/health/history/media queries; pin the new keyword mappings.
4. **Integration smoke for drishti**: `python -m drishti_engine.main` starts the MCP server; verify `search_flights`/`graphic_art` register as tools in the CLI at startup (config.yaml already lists `drishti`).
5. **mypy cleanup** (optional): address the 8 remaining pre-existing errors, e.g. guard `proc.stdout/stderr`/`Process | None` in `veda_engine/tools/shell.py` (239/242/251) and the `phase: str` Literal mismatch in `runner.py` (585/587), plus `code_interpreter.py:229/262`.
