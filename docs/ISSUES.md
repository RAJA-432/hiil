# H.I.I.L. — Known Issues Register

Deep-review findings for the **backend** (`vajra_gate`), **CLI core** (`mcp_cli`), and
**AI workspace** (`veda_engine` + `setu_bridge`) components, plus a CLI/UI integration
surface audit (I-series below).

- Reviewed at: commit `d78f446` (working tree).
- Method: static source review + targeted runtime verification. Every finding below
  was confirmed against the actual code; `CRITICAL` items were verified directly.
- File:line references point at `HEAD`; line numbers may drift.
- Status legend: `OPEN` = unfixed at time of writing. This register supplements the
  earlier report in `docs/DEEP_RESEARCH.md` (commit `63fbc7f`); items fixed there are
  not re-listed.

---

## Critical

### C1 — Auth is a no-op; every "protected" endpoint is effectively public
**Status: OPEN**

`vajra_gate/auth.py:41-57` — `get_current_user()` returns the literal string
`"default"` when no/invalid credentials are present instead of raising
`HTTPException(401)`. Every router declares `user: str = Depends(get_current_user)`,
so register/login JWTs (24 h, HS256) are decorative. Anyone who can reach the server
gets full access to `/api/tools/call` (arbitrary tool invocation incl. `write_file`),
agent spawn/run, cron creation, A2A, KV store, rewards, and the WebSocket chat.

**Fix:** raise `HTTPException(401)` when no valid token is present; stop returning
`"default"`. Set `request.state.user` so the rate limiter and access log see the real
identity.

### C2 — Path traversal via prefix-match in `FileSystem.resolve`
**Status: OPEN**

`vajra_gate/services/filesystem.py:23-27`:

```python
resolved = os.path.realpath(os.path.join(self._root, path))
if not resolved.startswith(self._root):
    raise PermissionError(...)
```

`startswith` without a separator allows escaping to any sibling path sharing the
root's name prefix. With root `...\hiil`, `..\..\hiil_evil\secret.txt` resolves to a
path that *does* start with the root string and passes the check. Combined with C1 and
the unauthenticated file endpoints (see H1), this yields arbitrary file
read/write/delete outside the workspace.

**Fix:** `if not (resolved == self._root or resolved.startswith(self._root + os.sep)):`
(and normalize case on Windows).

### C3 — KV-store namespace is an unsanitized filesystem path
**Status: OPEN**

`vajra_gate/store.py:107,121` — `path = self._dir / f"{namespace}.json"` uses the
client-supplied `namespace` directly. `routers/langgraph.py:316-358`
(`PUT /store/items`) passes it through untouched. A namespace such as
`..\..\AppData\Roaming\sensitive` lets `_load` **read** any existing `.json` file and
`upsert` **overwrite** any `.json` file with attacker-controlled JSON.

**Fix:** validate namespace against a strict pattern
(`^[A-Za-z0-9_.-]{1,64}$`); reject path separators and `..`.

### C4 — Shell-tool denylist is trivially bypassable (sandbox escape)
**Status: OPEN**

`veda_engine/tools/shell.py:18-30,101-103` — the guardrail is a regex denylist that
matches only specific spellings. Verified bypasses:

```
rm --recursive --force .   # long options
rm -r -f *                 # flags split across tokens
rd /q /s .                 # flag order re-arranged
rm -rf ~                   # target not in [/\\*]
cd C:\Users\rajas && rd . /s /q   # cd is not blocked at all
```

The tool's docstring advertises a "sandbox" that does not exist. The command runs via
`asyncio.create_subprocess_shell` (`shell.py:133`); only `cwd` is validated, and an
internal `cd` can leave it.

**Fix:** stop regex-blocking. Reject destructive verbs outright (`rm`, `del`, `rd`,
`rmdir`, `Remove-Item`, `format`, `mkfs`, `dd`, `shutdown`, ...) regardless of flags;
reject `cd` outside the validated cwd; reject `>`/`>>` redirections that escape the
workspace and `&&`/`||`/`;`/pipe chaining; or parse with a real shell parser and
deny-list on `argv[0]` + resolved target.

### C5 — `read_dir` root-confinement control fails OPEN
**Status: OPEN**

`veda_engine/tools/roots.py:33-37`:

```python
try:
    roots_result = await ctx.session.list_roots()
except Exception:
    logger.warning("list_roots failed, allowing access")
    return True
```

When the client doesn't support `list_roots` (or the call fails for any reason), access
to **any directory on the host** is granted. This is the opposite of fail-safe and is
inconsistent with `_walk_files`-based tools, which confine to `WORKSPACE_ROOT`.

**Fix:** fail closed (`return False` on any exception).

### C6 — SSRF bypass in `web_fetch` via IPv4-mapped IPv6
**Status: OPEN**

`veda_engine/tools/web.py:53-97` — `::ffff:127.0.0.1` and `::ffff:169.254.169.254` are
`IPv6Address` objects and match none of the IPv4 networks in `_PRIVATE_NETWORKS`
(verified: `.is_private` is `True`, membership is `False`), so they pass validation and
reach loopback / cloud-metadata. DNS-rebinding also remains: `_validate_url` resolves
once, then `httpx` re-resolves the hostname on connect (`web.py:125`), so an
attacker-controlled domain can alternate DNS answers.

**Fix:** normalize mapped addresses before checking (`if ip.ipv4_mapped:
ip = ip.ipv4_mapped`), and resolve once + connect to the validated IP directly.

---

## High

### H1 — File-API endpoints are unauthenticated
**Status: OPEN**

`vajra_gate/routers/files.py:52-106` — none of `read_file`, `list_directory`,
`write_file`, `create_directory`, `delete_file`, `rename_file` declares
`Depends(get_current_user)`. Combined with C1 and C2 this is unauthenticated arbitrary
file read/write/delete.

**Fix:** add `user: str = Depends(get_current_user)` to every handler (or a router-level
`dependencies=[...]`).

### H2 — `/threads/{id}/runs/stream` hangs forever if `chat.send` fails
**Status: OPEN**

`vajra_gate/routers/langgraph.py:186-194` — `_run()` calls `chat.send(...)` with no
`try/finally` that pushes a `"done"` event; `chat.send` only signals done on success
paths. On exception the `async for event in bus.events()` never terminates and the
client connection hangs indefinitely. (Contrast `vajra_gate/chat.py:131-142`, which gets
this right.)

**Fix:** mirror `chat.py` — wrap `send` in `try/finally` pushing `done`; cancel the task
on generator close.

### H3 — Shared pooled chat mutated without lock → cross-thread context corruption
**Status: OPEN**

`routers/langgraph.py:133-281`, `routers/sessions.py:92-93`, `routers/chat.py:82`,
`crons.py:101-104` — LangGraph thread/session endpoints reuse the pool's single
`default` chat and assign `chat.session_id` / `chat.messages` *outside* the per-chat
`asyncio.Lock` (which only wraps `send()`). Two concurrent requests for different
threads interleave these mutations, so one thread's history can leak into another
thread's LLM context.

**Fix:** load/mutate messages under the chat lock, or create a dedicated pooled chat per
thread (`pool.get(thread_id)`).

### H4 — `grep` reads symlinked files without path confinement
**Status: OPEN**

`veda_engine/tools/workspace.py:110-131` — `_walk_files` (lines 41-61) includes symlink
*files* (only directory symlinks are skipped). `grep` then does
`path.read_text("utf-8", errors="replace")` (line 120) with **no `resolve()` +
`is_safe_path()` check**, unlike `read_text_resource` (146-149) and `read_text_batch`
(183-186). A symlink inside the workspace pointing outside exfiltrates external file
contents to the model.

**Fix:** resolve each candidate and apply `is_safe_path(path, WORKSPACE_ROOT)` before
reading; skip non-regular files.

### H5 — Agent runner: interrupt corrupts conversation; `resume()` is dead code
**Status: OPEN**

`mcp_cli/services/agents/runner.py` — (a) lines 320-321 append tool results only if
`_execute_tool_calls` completes; the `AgentInterruptError` at line 375 aborts mid-batch,
so no tool messages are recorded for any pending `tool_calls`. (b) `_resume_event` is
set at lines 167 and 223 but **never awaited anywhere** — `resume()` is dead code and a
gated agent stays stuck forever. (c) Agent memory persistence is unreachable (nothing
writes `.agent_memory/`), and even if reached, the extraction slice at line 484 takes
the wrong part of the file.

**Fix:** append recorded tool messages before raising the interrupt; await `_resume_event`
in the gating loop; fix the memory persistence path.

### H6 — File reads have no size cap (memory exhaustion / giant payloads)
**Status: OPEN**

`veda_engine/tools/workspace.py` — `read_text_resource` (156-161) reads the entire file
and returns it; `read_text_batch` (194-212) fully buffers up to 20 files before
truncating the payload; `grep` (118-121) reads every candidate fully.

**Fix:** `os.stat` the target and reject/skip files above a hard size limit, or read
incrementally (first N bytes) and truncate while streaming.

### H7 — `mock_mail.list_messages("drafts")` crashes with `KeyError: 'read'`
**Status: OPEN**

`setu_bridge/mock_mail.py:137` reads `msg["read"]` for every item, but records created
by `send_draft` (171-178) and `save_draft` (199-207) have no `read` key. First draft
created ⇒ `list_messages(folder="drafts")` raises an unhandled exception.

**Fix:** use `msg.get("read", False)` in `list_messages`/`get_message`, or set
`"read": False` in both record constructors.

### H8 — `ManagedConnection.connect()` leaks subprocess/streams on handshake failure
**Status: OPEN**

`setu_bridge/connection.py:76-132` — contexts are entered into `self._exit_stack` as
connect proceeds, but if `initialize()` raises, `__aexit__` is never invoked (only
`__aenter__` raised), leaking the stdio subprocess and pipe streams per failed attempt.
There is also no timeout around `stdio_client` / `session.initialize()`, so an
unresponsive server hangs the caller forever.

**Fix:** wrap the connect body in `try/except BaseException:
await self._exit_stack.aclose(); raise`; add `asyncio.wait_for` around the handshake.

---

## Medium

| # | Location | Issue |
|---|----------|-------|
| M1 | `vajra_gate/middleware/rate_limit.py:13-30` | Raising `HTTPException` inside `BaseHTTPMiddleware` yields **500 instead of 429**; `request.state.user` is never set so user-based limiting never engages; spoofable `X-Forwarded-For` rotates the IP key. |
| M2 | `vajra_gate/routers/auth.py:12,21`; `mcp_cli/services/users.py:28` | `scrypt(n=16384)` runs **synchronously in async handlers** — blocks the event loop; concurrent logins are a DoS. |
| M3 | `vajra_gate/crons.py:86-112` | Cron loop is a single task with **no timeout** — one hung `chat.send` stalls all jobs; mutates the shared pooled chat without its lock. |
| M4 | `vajra_gate/chat_pool.py:72-81`; `mcp_cli/services/chat.py:287-292` | Session id = `session_%Y%m%d_%H%M%S` (second resolution) — two `POST /api/session/new` in the same second collide, overwrite each other, and leak the first chat. |
| M5 | `vajra_gate/routers/knowledge.py:21-36` | `await file.read()` with no size cap and no `Content-Length` check — multi-GB uploads exhaust memory. |
| M6 | `vajra_gate/routers/chat.py:29-30` | Unvalidated client `session_id` creates a brand-new `CliChat` per unseen id, each running expensive `initialize()` (MCP refresh). Spam = repeated expensive setup. |
| M7 | `vajra_gate/metrics.py:46-59` | Request path interpolated unescaped into Prometheus labels — `"` / `%0A` inject arbitrary lines into `/metrics`. |
| M8 | `vajra_gate/routers/agents.py:86-107`; `langgraph.py:189-194` | Agent runs launched via fire-and-forget `asyncio.create_task` are **never cancelled on client disconnect** — keep running (and billing) in the background. |
| M9 | `vajra_gate/store.py:165-187`; `services/reward.py:420-457` | `rewards.jsonl` grows unbounded (full snapshot per upsert); reward metrics truncate at 10k events **before** the `since` filter, silently undercounting. |
| M10 | `vajra_gate/store.py:101-124` | KVStore: non-atomic JSON writes (crash corrupts file), uncaught `JSONDecodeError` on load takes down tools, process-local cache ⇒ multi-process lost updates. |
| M11 | `vajra_gate/services/filesystem.py`, `storage.py:21-39`, `store.py` | Blocking sync file I/O (`os.stat`, `os.listdir`, JSON writes, tree walks) inside async handlers blocks the event loop. |
| M12 | `vajra_gate/routers/auth.py:19-30` | First-user bootstrap is check-then-act across two connections (TOCTOU race); `register_user` accepts 4-char passwords. |
| M13 | `vajra_gate/middleware/logging_middleware.py:98-138` | `raise` before the shared log/metrics block drops all 5xx from access log and `hiil_http_requests_total`. |

---

## Low

| # | Location | Issue |
|---|----------|-------|
| L1 | `routers/langgraph.py:112-294` | Dead 404 checks — `history.async_load_session` returns `[]` for missing sessions, never `None`; random thread ids return 200 with 0 messages. |
| L2 | `routers/sessions.py:86-97` | `switch_session`/`delete_session` accept nonexistent sessions (200 with empty history). |
| L3 | `vajra_gate/chat.py:33-35` | 500 detail reflects raw exception strings (paths/API info leak). |
| L4 | `vajra_gate/__init__.py:84-92` | Default CORS includes dev origin `http://localhost:5173` with `allow_credentials=True`. |
| L5 | `chat_pool.py:46-48`, `__init__.py:51` | `AsyncExitStack` leaked if pool prewarm fails/times out; prewarm swallows all non-cancellation failures. |
| L6 | `routers/sessions.py:47-49`, `langgraph.py:352-359` | Unvalidated `limit`/negative `offset`; unbounded `StoreSearchRequest.limit`. |
| L7 | `routers/chat.py:77-83` | `set_model` accepts any string with no validation. |
| L8 | `chat_pool.py:104-110` | Stale `_state._chat` reference after LRU eviction until next `_require_chat`. |
| L9 | `routers/chat.py:93` | `/api/usage` calls sync `total_summary()` on the event loop. |
| L10 | `routers/misc.py:32-37` | `/api/workspace` returns absolute `WORKSPACE_DIR` unauthenticated. |
| L11 | `veda_engine/tools/workspace.py:124` | `grep` docstring promises `file:line:content` but emits `file:content` (no line number). |
| L12 | `setu_bridge/mock_mail.py:81,179,208` | `_MAX_DRAFTS = 500` declared but never enforced — unbounded memory growth. |
| L13 | `setu_bridge/mock_mail.py:125-128` | Unknown folder names silently fall back to inbox (typos hidden). |
| L14 | `veda_engine/tools/shell.py:156-168` | `asyncio.wait(readers, timeout=timeout)` can double the timeout and discard *both* streams if a reader lags; cancelled tasks never awaited (`Task was destroyed` warnings). |
| L15 | `veda_engine.py:12-13` | Launcher removes its own directory from `sys.path`; `python veda_engine.py` from a checkout without an editable install fails with `ModuleNotFoundError`. |
| L16 | `veda_engine/config.py:5` | `WORKSPACE_ROOT` silently follows the startup CWD; no `HIIL_WORKSPACE` override to pin the security boundary. |
| L17 | `veda_engine/tools/summarize.py:18-29` | Unbounded `text_to_summarize` input, hardcoded 4000-token budget. |
| L18 | `veda_engine/tools/preferences.py:49-50` | Full file rewrite per key, sync I/O on the event loop. |
| L19 | `setu_bridge/config.py`, `veda_engine/prompt_manager.py` | Empty placeholder modules (1 line each). |
| L20 | `validation.py:7` | `API_BASE = "http://127.0.0.1:8000"` hardcoded; `self.results` accumulated but never read. |
| L21 | `veda_engine/tools/workspace.py:78,95,204` | Silent truncation (`matches[:50]`, `matches[:200]`, `paths[:_MAX_BATCH_FILES]`) with no indicator. |

---

## Integration gaps — CLI / UI surface audit

Review of which backend "processes" (subsystems/servers) are only **partially**
integrated with the final CLI (`mcp_cli`) and the React SPA (`canvas_app/frontend`).
Surfaces: **CLI** = `mcp_cli` slash commands / REPL; **UI** = `canvas_app` React SPA;
**API** = `vajra_gate` HTTP endpoints. "Partial" = reachable from one surface only, or
gated off / non-functional by default.

### I1 — Setu Bridge Mock Mail & Calendar MCP servers: CLI-only, no UI surface
**Status: OPEN**

Wired into the CLI via `SetuBridge` (`mcp_cli/services/chat.py:32`,
`mcp_cli/services/server_manager.py:14`) and used by the `inbox-manager`,
`quote-reviewer`, and `calendar-agent` sub-agents
(`mcp_cli/services/agents/subagents.py:32-113`). The UI exposes **no** mail or calendar
panel — the only trace is a decorative, disabled plugin card
(`canvas_app/frontend/src/components/Skills/ConnectorsPanel.jsx:10`,
`{ id: 'email', ..., enabled: false, type: 'plugin' }`). Also see H7 (`drafts`
`KeyError: 'read'`) and L12/L13 for server-side gaps.

**Fix:** ship a real connectors surface (mail triage + calendar panels) backed by the
existing `/api/tools/call` path, or drop the misleading plugin card.

### I2 — Intent routing, preference memory, and the calendar agent: gated OFF by default
**Status: OPEN**

The rule-based + LLM classifier (`mcp_cli/services/agents/route_classifier.py`), the
`SUBAGENT_REGISTRY` (incl. `calendar-agent`), and preference-memory wiring are all
present but disabled unless `intent_routing: true`
(`mcp_cli/config.py:127-129`, `Settings.intent_routing`). The CLI exposes no command to
toggle it, and the UI has no setting for it.

**Fix:** surface an intent-routing toggle in the CLI (`/intent`) and the UI settings
modal, or enable it by default once the classifier is hardened.

### I3 — A2A registry & message inbox: API-only
**Status: OPEN**

`vajra_gate/a2a.py` + `/a2a/*` endpoints (`vajra_gate/routers/phase_c.py:322-405`)
implement agent discovery, messaging, and read-receipts. No CLI command and no UI panel
reference them (verified: zero matches for `a2a` in `canvas_app/frontend/src`).

**Fix:** decide whether A2A is a public feature; if so add a CLI view and a UI inbox
panel, otherwise document it as an internal/API surface only.

### I4 — Cron scheduler: API-only
**Status: OPEN**

`vajra_gate/crons.py` + `/crons/*` (`vajra_gate/routers/phase_c.py:136-183`) run a
30 s-poll in-memory scheduler. No CLI or UI surface (zero frontend matches for `cron`).
Also see M3 (no job timeout; mutates pooled chat without its lock).

**Fix:** add a minimal UI panel (list/create/delete jobs) or document as API-only;
fix M3 while touching it.

### I5 — Rewards / economy tier: partially wired (UI feedback only)
**Status: OPEN**

The UI posts thumbs feedback to `/api/rewards`
(`canvas_app/frontend/src/api/chat.js:87` `sendFeedback`), but `/api/rewards/metrics`
and the reward list (`vajra_gate/routers/rewards.py`) are never consumed by the UI, and
the CLI has no rewards command. Also see M9 (unbounded `rewards.jsonl`, metrics
truncated at 10k events).

**Fix:** either show reward metrics somewhere (UI panel or `/rewards` CLI command) or
drop the half-wired feedback call.

### I6 — Auth / users / JWT: API-only and effectively a no-op
**Status: OPEN**

`vajra_gate/auth.py` + `/api/auth/*` routers. The UI has no login flow, and C1 makes
the whole layer decorative (`get_current_user` returns `"default"`). Users are
exercisable only via raw HTTP.

**Fix:** enforce 401s (C1) first; then decide whether to ship a login UI or keep
auth headless behind the gateway.

### I7 — WebSocket `/ws` chat: unused by the UI
**Status: OPEN**

`vajra_gate/routers/phase_c.py` implements a WebSocket chat at `/ws`, but the SPA uses
SSE streaming (`POST /api/chat?stream=1`, `canvas_app/frontend/src/api/chat.js:15`).
The `/ws` path is dead in practice.

**Fix:** remove it or promote it to a first-class transport (streaming audio,
bidirectional edits); document whichever wins.

### I8 — Safety gates (verifier / moderation / discovery guard): default-OFF, CLI-only
**Status: OPEN**

`enable_verification`, `enable_moderation`, and `discovery_guard` exist
(`mcp_cli/config.py`, `Services.verifier.py` / `moderation.py` / `discovery`) and are
wired in the CLI path, but all default to disabled/`off`. The UI exposes none of them.

**Fix:** add toggles to the UI settings modal (and/or `/verify`, `/moderate` CLI
commands) so operators can enable them without editing `config.yaml`.

### I9 — Agent HITL interrupt/resume: UI present, backend `resume()` dead code
**Status: OPEN**

The UI handles `interrupt` events and shows approval options
(`canvas_app/frontend/src/components/Agents/AgentRunModal.jsx:100-171`), but the
backend `AgentRunner.resume()` is never awaited (`_resume_event` set but never consumed)
so a gated agent stalls forever — see **H5**. The CLI `/agent` command also does not
implement the create/search/approve/respond workflow from
`docs/superpowers/specs/2026-07-21-clarified-agent-cli-design.md`.

**Fix:** land H5's resume wiring, then align the CLI `/agent` subcommands with the spec.

### I10 — Agent memory persistence: unreachable
**Status: OPEN**

Nothing writes `.agent_memory/` (see **H5c**), so the agent memory feature has no effect
from either surface.

**Fix:** implement the persistence write path (per H5), then surface recall/preview in
CLI and UI.

### I11 — veda_engine shell / web / workspace tools: CLI full, UI partial
**Status: OPEN**

All veda_engine tools are exposed in the CLI (`mcp_cli/services/builtin_tools.py`). The
UI surfaces only the workspace/file tree (`api/files.js`, `api/workspace.js`) and the
tool-activity log (`ToolActivityPanel.jsx`); shell and `web_fetch` have no interactive
UI surface. See C4/C5/C6/H4/H6 for the underlying tool bugs.

**Fix:** no UI work required unless shell/web become user-facing; otherwise document the
surface split.

### I12 — PWA / service worker: intentionally not wired
**Status: OPEN (by design)**

The SPA ships manifest + icons but service-worker registration is deliberately not
wired (the gateway serves the app under `/canvas/` only) — `README.md:200`.

**Fix:** none intended; document as a known limitation.

---

## Fixed after initial audit

### S1 — FIXED — `/api/session/switch` 422 on every conversation click
`canvas_app/frontend/src/components/Sidebar/ConversationItem.jsx:53,59` calls
`onSelect(conversation.id)` (a plain **string**), but
`canvas_app/frontend/src/context/ChatContext.jsx`'s `handleSelectConversation` treated
its argument as a conversation **object** and read `conv.id` off it → `undefined` →
`apiPost` serialized `{session_id: undefined}` to `{}` → FastAPI 422 on every switch.
`switchConversation(conv.id).catch(() => {})` swallowed the error, so the UI showed the
conversation as selected while the backend never switched.

**Fix (applied):** `handleSelectConversation` now normalizes both shapes — accepts a
string id or a conversation object, resolves the id, and bails on missing ids. Frontend
rebuilt; all 35 vitest tests pass. (Pre-existing bug at HEAD — unrelated to the backend
fixes in this register.)

---

## Frontend Lighthouse audit (`http://127.0.0.1:8000/canvas/`)

Lighthouse 13.3.0, desktop emulation. Scores: **Performance 0.88**, Accessibility 1,
Best Practices 1, SEO 1, Agentic Browsing 0.83. FCP 0.7s, LCP 1.2s, TBT 0ms, TTI 1.2s,
SI 0.7s. 17 requests / 214 KiB.

### F1 - FIXED - CLS 0.188 (Cumulative Layout Shift, perf sub-score 0.65)
**Status: FIXED**

The only score-driving defect. Two layout shifts; primary culprit
`main#main-content > div.chat-messages > div.chat-empty > div.arch-card`
(654px-tall empty-state H.I.I.L. architecture card), score 0.1875; secondary
`header > div.toolbar > div.model-picker > ::after` (negligible). The card shifted at
~533ms, preceded by a 62ms long task (lazy chunk arrival).

**Root cause:** `.chat-panel` is a grid item in the `auto 1fr auto` layout's `1fr`
chat row, and `.chat-messages` is a flex item inside it. Both defaulted to
`min-height: auto`, so they could not shrink below the arch-card's content height.
When lazy chunks mounted, the row/container inflated then re-centered the card,
shifting it.

**Fix (applied) in `canvas_app/frontend/src/styles/chat.css`:**
- `.chat-panel`: added `min-width: 0; min-height: 0;` (grid item can shrink to its
  `1fr` track).
- `.chat-messages`: added `min-height: 0` (flex item can shrink and scroll instead of
  forcing the row taller) and `overflow-anchor: none` (no scroll-anchoring jumps).
- `.chat-empty`: `height: 100%` → `min-height: 100%` so centering never depends on a
  late-settling parent height.
- Rebuilt (`npm run build`); 35/35 vitest pass. Re-run Lighthouse to confirm CLS ≤ 0.1.

### F2 - INFORMATIVE (weight-0, not scored) - Render-blocking CSS
`index-*.css` is render-blocking (~40ms est savings). Fine for a SPA; no action taken.

### F3 - INFORMATIVE (weight-0, not scored) - Unused JS in vendor-markdown chunk
`vendor-markdown-*.js` (~148 KiB gzip) is the lazy-loaded markdown/streaming chunk;
usage is conditionally weighted by the audit. No action taken.

### F4 - FIXED - Missing security headers
**Status: FIXED**

No CSP, HSTS, COOP, X-Frame-Options/frame-ancestors, or Trusted Types headers.
All flagged "High" but weight-0 (do not affect score).

**Fix (applied):** new pure-ASGI `SecurityHeadersMiddleware` in
`vajra_gate/middleware/security.py` injects headers on every response — including
streaming/SSE responses, which a plain `BaseHTTPMiddleware` return value would not
cover:
- `Content-Security-Policy`: `default-src 'self'; script-src 'self' 'unsafe-eval'
  https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  img-src 'self' data: blob: http: https:; font-src 'self' data: https://cdn.jsdelivr.net;
  connect-src 'self' https://cdn.jsdelivr.net; worker-src 'self' blob:
  https://cdn.jsdelivr.net; object-src 'none'; base-uri 'self'; frame-ancestors 'self';
  form-action 'self'` (overridable via `HIIL_CSP`).
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Frame-Options: SAMEORIGIN`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`

`'unsafe-eval'` and `https://cdn.jsdelivr.net` in `script-src` are required by the
Monaco editor AMD loader (its `loader.js` uses `eval`/`new Function`, and it loads from
the jsdelivr CDN); `style-src 'unsafe-inline'` is required by inline splash styles and
Monaco's injected stylesheet. The two inline `<script>` blocks previously in
`index.html` (error fallback + theme init) were moved to `public/error-fallback.js` and
`public/theme-init.js` so `script-src` needs no `'unsafe-inline'`.

Trusted Types was not enforced: enforcing `require-trusted-types-for 'script'` would
break the inline-HTML error fallback and Monaco's DOM usage. Added
`tests/test_security_headers.py` (3 tests: plain + streaming header presence, CSP
restrictiveness). Verify with Lighthouse.

---

## Recommended remediation order

1. **Auth enforcement (C1)** — everything else is downstream of this.
2. **Filesystem path traversal (C2) + store namespace (C3) + file-API auth (H1)** —
   arbitrary file read/write outside the workspace.
3. **Shell tool (C4)** — replace the denylist with deny-by-verb + parsed-command checks.
4. **Fail-closed roots (C5) + web_fetch SSRF (C6)** — network/file boundary hardening.
5. **Streaming hang (H2) and shared-chat races (H3)** — concurrency correctness.
6. **Rate limiter (M1)** — correct status codes + real per-user keying.
7. **Run the full gate:** `make check` (lint + typecheck + test) after any fix.
