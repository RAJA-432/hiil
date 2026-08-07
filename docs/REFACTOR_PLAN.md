# Refactor Plan — Complexity Reduction

Reference plan for reducing cyclomatic complexity in the highest-complexity modules of
H.I.I.L. (measured with the AST analysis script `scripts/analyze_complexity.py`).

## Baseline metrics (Phase 0 snapshot)

| Function | Location | maxCC |
|----------|----------|-------|
| `send` | `mcp_cli/services/chat.py:544` | 52 |
| `handle_agent_cmd` | `mcp_cli/commands/agent.py:12` | 43 |
| `_execute_loop` | `mcp_cli/services/agents/runner.py:262` | 32 |
| `run` | `mcp_cli/ui/app.py:129` | 29 |
| `trim` | `mcp_cli/services/context_manager.py:56` | 29 |
| `run_command` | `veda_engine/tools/shell.py:241` | 29 |

## Phase 0 — Baseline & Guardrails (0.5 day)

1. Run the gate: `make check` (ruff → mypy → pytest). Record any pre-existing failures.
2. Capture the CC/LOC snapshot with `scripts/analyze_complexity.py`.
3. Confirm test coverage for modules under refactor:
   `test_context_manager.py`, `test_agent_cmd.py`, `test_agent_runner.py`,
   `test_agent_lifecycle.py`, `test_chat_pipeline.py`, `test_cli_phases.py`, `test_shell.py`.
4. **Contract pins** (must not change during refactor):
   - `ContextManager.trim(messages, tools_token_count=0) -> list[dict]` — pure, no I/O.
   - `handle_agent_cmd(chat, subcmd, rest, prompt_async) -> str`.
   - `AgentRunner._execute_loop(task_input=None) -> str`.
   - `CliChat.send(user_input, images=None, on_tool_event=None, on_chunk=None, on_approval=None, notification_bus=None, response_format=None) -> str`.
   - `run_command(command, cwd=".", timeout=30, ctx=None) -> str` (veda_engine shell tool).
   - `App.run()` (REPL loop).

## Phase 1 — `ContextManager.trim` algorithmic rewrite (1 day)

- Add a fuzz/parity test first: property test comparing old vs new `trim` on randomized
  message lists, using the existing `NoCacheCM` reference pattern (`test_context_manager.py:150`).
- Keep: budget math, suffix-sum array, binary search for kept suffix, truncation heuristics.
- Replace: `pop(0)`/`insert(0)` shifts → index offsets + single final list build; the
  100-pass `max()` scan → `heapq` max-heap of truncatable candidates (`O(k log k)`).
- Benchmark on a synthetic 10k-message corpus; assert identical output token counts.
- Run `pytest tests/test_context_manager.py`, then `make check`.
- **Exit criteria:** parity fuzz passes; CC ≤ ~10; gate green.

## Phase 2 — `commands/agent.py` table-driven dispatcher (0.5 day)

- Extract traversal guard into `_path_guard(subcmd, rest)`, applied once before dispatch.
- Build `_AGENT_COMMANDS: dict[str, Handler]`; extract `_create_agent`, `_list_agents`,
  `_search_agent`, `_pause_agent`, `_approve_agent`, `_reject_agent`; keep
  `_handle_registered` for registry-backed `agents`/`run`.
- Add `_agent_dir(name)` helper to remove 3x repeated path construction.
- Extend `test_agent_cmd.py`: traversal-block per path subcommand; unknown-subcommand; one
  test per handler with fake `prompt_async`.
- **Exit criteria:** dispatcher CC ≤ 5, handlers ≤ 6; every existing return string identical.

## Phase 3 — `AgentRunner._execute_loop` step extraction **+ H5 fix** (1–1.5 days)

Refactor and the H5 interrupt/resume bug touch the same lines; do them together.

- Extract steps (behavior-preserving, committed separately): `_bootstrap`, `_chat_once`,
  `_settle_response`, `_maybe_summarize`, `_apply_tool_results`.
- **H5 fix:** move `self._messages.extend(results)` before raising `AgentInterruptError`
  (`runner.py:427-429`); verify `resume()` path awaits `_resume_event`; add integration test
  (pause on `interrupt_on` tool → `resume(decisions)` → completes).
- Split `_execute_tool_calls` (CC 24): `_parse_args`, `_perm_gate`, `_hitl_gate`.
- Fix memory-persistence path (H5c): make `_persist_memory` write `.agent_memory/` and
  correct the extraction slice (`runner.py:484`).
- **Exit criteria:** `_execute_loop` CC ≤ 10, `_execute_tool_calls` CC ≤ 10; H5 regression
  tests pass; resume works in CLI.

## Phase 4 — `CliChat.send` phase pipeline (2 days, largest surface)

Safe only after trim + runner are stable.

- Lock the surface with contract tests in `test_chat_pipeline.py` (moderation-block,
  intent-route, max-iterations, correction-retry, verifier-revise paths).
- Extract `_prepare_input(user_input, images, bus) -> Prepared | None` (sanitize/moderation,
  intent routing, doc-inject + RAG, auto-index spawn, OCR/vision branch). `None` = blocked.
- Extract `_tool_loop`: `_call_llm`, `_settle_output` (validation/correction/finalize),
  `_run_tools` (state push + `tool_runner.execute_tool_calls` + extend).
- `send` becomes orchestration only (~35 lines). Keep private-method ordering stable for
  existing `@patch`-based tests.
- **Exit criteria:** `send` CC ≤ ~8, each new method ≤ 10; bus event sequence, token
  accounting, and return strings identical.

## Phase 5 — `ui/app.py:run` + `veda_engine/tools/shell.py` (1.5 days)

- `app.py`: extract `_get_input()` (prompt/timeout/EOF), hoist `_consume_phases(bus, phases)`
  from nested closure, extract `_handle_message(user_input)` (streaming render + usage
  delta). `run` becomes the dispatch loop. Manual TTY smoke test + `test_cli_phases.py`.
- `shell.py`: extract `_spawn`, `_await_exit` (wait + kill-tree fallback), `_drain_outputs`
  (reader dance). Keep `_deny_reason` as single policy entry; drop redundant inline
  `_DENIED_PATTERNS` fallback only if covered. Run `test_shell.py`, `test_workspace_tools.py`.
- **Exit criteria:** CC `run` ≤ 10, `run_command` ≤ 12; all `[denied]`/`[error]`/`[timeout]`
  strings and cleanup paths (normal/timeout/CancelledError) preserved.

## Phase 6 — Verification & Ship

1. Re-run `scripts/analyze_complexity.py`; update `docs/COMPLEXITY.md` hotspot table.
2. Update `docs/ISSUES.md`: mark **H5** FIXED; remove I-series items this plan resolves
   (I9, I10); keep others.
3. Full gate: `make check` (Python 3.13 & 3.14 per CI matrix).
4. **Commit discipline:** one commit per phase (each green), repo-style conventional
   prefixes (`perf:`, `refactor:`, `fix:`).

## Risk register

| Risk | Mitigation |
|---|---|
| `send` refactor breaks bus event order (UI relies on it) | Phase 0 contract tests + phase 4 event-sequence assertions |
| `trim` parity drift | NoCache reference + fuzz parity test first |
| H5 fix changes interrupt UX | Integration test: pause → resume → complete; manual CLI check |
| mypy strictness on new types | `make typecheck` per phase |
| Windows-only subprocess differences (shell.py) | Preserve `os.name` branches; CI covers via pytest |

**Suggested start:** Phase 1 (`trim`) — smallest risk, self-contained, immediately verifiable.
