# H.I.I.L. — Deep Research Report

Comprehensive technical review of the **H.I.I.L. (Hyper-Integrated Inference Engine)**
codebase at commit `63fbc7f`, covering `mcp_cli`, `vajra_gate`, `veda_engine`,
`setu_bridge`, and `canvas_app/frontend`.

> **Scope note:** this is a static code review (source read + verified traces), not a
> runtime load test. File/line references point at `HEAD`; line numbers may drift.
> LOC figures are approximate physical/non-blank lines as reported per module.

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Backend Python source | ~13,700 LOC across `mcp_cli` (9,637), `vajra_gate` (~3,100), `veda_engine` (~1,065), `setu_bridge` (~890) |
| Frontend | ~9,700 LOC across 105 source files (56% CSS) |
| Backend tests | 509 (pytest) |
| Frontend tests | 10 files, 35 tests (Vitest) |
| Runtime deps (frontend) | 7 |
| Verified bugs | 1 confirmed (agent tool routing) — **FIXED**; 3 high-confidence functional/security gaps — **all FIXED** |

**Verdict:** a well-layered, security-conscious MCP chat platform with strong
defense-in-depth and a disciplined, dependency-light frontend. The main risks were
concentrated in (a) a verified agent-tool-routing defect that silently disables two
agents, (b) a documented SSRF redirect bypass, (c) soft/optional auth everywhere, and
(d) thin frontend test coverage of the most critical paths. **All of (a), (b) and (d)
have since been fixed** (see §4); the remaining risks are concentrated in the
auth/economy tier (see §5).

---

## 2. Architecture

```
CLI / React SPA ──▶ FastAPI gateway (vajra_gate) ──▶ mcp_cli (CliChat / agents)
                                                        │
                                                        ├─▶ LLMClient ──▶ Ollama / OpenAI-compatible /v1
                                                        │        ├─ vision (image_url blocks)
                                                        │        └─ OCR fallback (tesseract)
                                                        ├─▶ RAG (chunker → embed → SQLite/FAISS IVF)
                                                        ├─▶ ToolRunner ──▶ SetuBridge ──▶ MCP servers
                                                        │        (veda_engine, mock_mail, calendar,
                                                        │         refiner, filesystem, memory, everything)
                                                        └─▶ NotificationBus ──▶ SSE / WS / JSONL / rewards
```

### 2.1 Data flow of a chat message

1. `CliChat.send()` (`mcp_cli/services/chat.py:522`) sanitizes input, gates on
   moderation, optionally routes intent to a sub-agent, expands `@docid` document
   injections, retrieves RAG context, auto-indexes the input, OCRs images for
   text-only models, and trims context to budget.
2. The tool loop (`chat.py:619-717`) streams the LLM reply; if tool calls are present,
   `ToolRunner.execute_tool_calls()` (`tool_runner.py:89`) dispatches through MCP
   servers (with permission + approval + discovery guards), appends results, and loops
   (max 10 iterations).
3. Output passes `_validate_output` (JSON-schema against `response_format`) and
   `_finalize_output` (verifier critique + moderation).
4. The gateway wraps this in a 4-task fan-out (`vajra_gate/chat.py:130-169`): chat
   run, JSONL audit recording, 5 s heartbeat, and reward scoring — all fed by one
   `NotificationBus`.

---

## 3. Component Deep-Dives

### 3.1 `mcp_cli` — Core Engine (9,637 LOC, 70 files)

**Entry & CLI.** `main.py` builds an `AsyncExitStack`, `create_chat(stack)`, and runs a
`prompt_toolkit` REPL (`ui/app.py:126`). Slash commands dispatch via `commands/router.py`
(30+ handlers); unknown `/foo` falls through to direct MCP tool invocation. There is
**no `[project.scripts]` entry point** — launched as `python -m mcp_cli.main`.

**`CliChat`** (`services/chat.py`, largest file at 635 LOC) is the orchestrator: holds
MCP `clients`, the `LLMClient`, history, usage, vector store, streamer, context
manager, RAG pipeline, document injector, discovery guard, tool runner, and the
`agents` dict.

**LLM layer.** `LLMClient` (`services/claude.py:69`) wraps `AsyncOpenAI` against a
provider base URL (Ollama default). Tenacity retry (3×, exponential backoff) on
5xx/network errors. Streaming yields `content` chunks then `tool_call`/`done`
(`claude.py:88-154`). Embeddings hit Ollama `/api/embed` or OpenAI `/embeddings` with an
LRU cache (cap 512). Vision capability is resolved at runtime from Ollama `/api/tags`
(5-min cache), not guessed from the name — unknown models default to vision-capable
(`chat.py:397-403`), which can send images to non-vision local models.

**RAG.** `chunker.py` (word-window 512/overlap 64, plus PDF via `pypdf`, DOCX via
`python-docx`). Two vector backends behind a `VectorBackend` Protocol: SQLite with an
**IVF k-means index** (`vector_store.py:36`, rebuilt every 50 inserts — O(n²) for large
corpora), and FAISS `IndexIDMap(IndexFlatIP)` with cosine-normalized on-disk indexes.
Auto-indexing (`context_manager.py:184`) writes every user input ≥ 20 chars into a
`"messages"` namespace with **no dedup / unbounded growth**.

**Context management.** `ContextManager.trim` (`context_manager.py:51-152`) is a
suffix-sum + binary-search budget fitter with up to 100 truncation passes, a
`[compacted #N]` system marker, and an overflow safety net. The former
**`hash()`-keyed token cache** (`context_manager.py:27` — process-salted, collision
prone, re-hashed `O(c)` on every access) is now keyed by a stable `sha256` content hash
(also fixed in `agents/memory.py`); in-place mutation of message dicts remains.

**Tool dispatch — two paths.** Main loop uses `ToolRunner` (`tool_runner.py`): converts
MCP `inputSchema` → OpenAI function schema, semaphore(4), 30 s timeout, permission
boundary via `RootsManager.inspect_tool_args`, JSON-arg recovery, discovery guard, and
an **approval gate** for sensitive tools (`frontier.py` whole-segment heuristic) —
now wired in the TTY path via `on_approval` (`ui/app.py`). Agents use `ToolRouter`
(`tool_router.py`) with per-agent capability filtering.

**Agent runtime** (`services/agents/`, 1,854 LOC). Deepagents-inspired:
`AgentConfig`/`AgentState`/`AgentResult` models, a `MiddlewarePipeline` with decorator
registry (`models.py:15`), and middleware for code interpretation (restricted builtins
+ subprocess + thread-timer timeout), exact Decimal quote calculation, todo tracking,
and summarization (fires at >30 messages or 85% token budget). The `AgentRunner`
(`runner.py`, 445 LOC) loops `max_iterations` with token-budget checks, HITL
interrupt/resume via `AgentInterruptError`, JSON-recovery for malformed tool args, and
per-agent file memory with snapshot-hash diffing. **Intent routing** is gated off by
default (`config.py:127-129`); when on, a rule-based + LLM classifier
(`route_classifier.py`) picks a sub-agent from `SUBAGENT_REGISTRY` (5 agents:
`chinook-analyst`, `inbox-manager`, `quote-reviewer`, `genre-researcher`,
`calendar-agent`).

### 3.2 `vajra_gate` — FastAPI Gateway (~3,100 LOC, 37 files)

**App factory & middleware** (`__init__.py`). Middleware stack (execution order):
CacheControl (immutable assets) → TrustedHost → RateLimit (token bucket, 10/s burst 20)
→ AccessLog (request_id, audit log for mutating/4xx+ ops) → GZip(500+) → CORS. A
lifespan prewarms the chat pool (0.5 s delay, 15 s cap). 12 routers registered.

**Endpoints.** ~60 endpoints across chat, auth, sessions, agents, skills, files,
knowledge, search, rewards, langgraph-compat, phase_c (metrics/ws/crons/mcp-tools/a2a),
and misc.

**SSE streaming.** `POST /api/chat` negotiates SSE via `Accept` header or `?stream=1`.
The `_merge_events` fan-out (`chat.py:130-169`) runs 4 concurrent tasks over one
`NotificationBus`: the chat run, JSONL audit (flush every 50 lines), 5 s heartbeat, and
reward observer. Token deltas are pushed with `push_tokens_nowait`; **there is no
server-side token throttle** — the "streaming render throttle" lives client-side (and
the client doesn't actually have one either — see §5).

**Auth.** JWT (HS256, 24 h) with an **ephemeral secret when `HIIL_JWT_SECRET` is unset**
— tokens silently break on restart. `get_current_user` returns `"default"` on any
failure (`auth.py:57`), so **every endpoint degrades to soft auth**. Rate limiting keys
on `request.state.user`, but nothing ever sets it — effective key is IP
(`X-Forwarded-For` → client host).

**LangGraph-compat.** `/threads` ≡ sessions, `/runs` ≡ `chat.send()`, `/store` ≡ a
file-backed `KVStore`. Includes a dead branch (`if body.metadata: pass`,
`langgraph.py:104`) and direct reach-through into `bus._queues`
(`langgraph.py:204-208`).

**A2A + cron + WS + MCP bridge** (`routers/phase_c.py`, 344 LOC). In-memory A2A bus
(`a2a.py`, capped at 10k messages, **no persistence** — agents/messages lost on
restart). In-memory cron scheduler (30 s tick vs min 10 s schedule → timing drift). A
WebSocket chat endpoint uses **fire-and-forget `ensure_future(websocket.send_json)`**
(`phase_c.py:78-84`). A REST `/mcp/tools` bridge exposes 6 `hiil_*` tools with a 6-way
if/elif dispatch and 500-char agent-result truncation.

**Rewards** (`services/reward.py`, 405 LOC). Gita-themed 7-dimension heuristic reward
system over `KVStore` (append-only `rewards.jsonl` for O(1) writes). Hard-coded
context-key conventions (`handled_gracefully`, `valid_args`) that only the stream
observer populates a subset of.

### 3.3 `veda_engine` — Built-in MCP Server (1,065 LOC)

`FastMCP("workspace-search")` (`main.py:37`) registers **17 tools** whose JSON schemas
are derived from Python type hints + docstrings.

| Group | Tools |
|-------|-------|
| Workspace | `search_resources`, `glob`, `grep`, `read_text_resource`, `read_text_batch`, `read_dir`, `list_roots` |
| Documents | `read_document`, `edit_document`, `format_document` (SQLite per-user store) |
| Preferences | `remember`, `recall`, `forget` |
| Web | `web_search` (DuckDuckGo), `web_fetch` (SSRF-guarded) |
| Shell | `run_command` (blacklist-guarded) |
| Other | `summarize` (client-side sampling), resources `docs://documents` |

**Path guard** (`tools/path_guard.py`): canonicalization rejecting NUL/control chars
and UNC/device paths, an internal `..` regex, and a second `resolve()`+containment check
at point of use (catches symlink escapes). Weaknesses: `roots.is_path_allowed` **fails
open** (`roots.py:35-37`), `read_dir` trusts client-advertised roots, and single-file
reads have no size cap.

**SSRF guard** (`tools/web.py`): scheme whitelist, host blocklist (cloud metadata,
localhost, `.internal`), literal-IP check, and full `getaddrinfo` A/AAAA resolution
tested against private networks. Redirects are followed manually (bounded at 5 hops) and
every hop is re-validated with the same rules before it is requested. No DNS-rebinding
protection (resolve and connect are separate).

**Shell tool** (`tools/shell.py`): regex denylist (`rm -rf /`, `dd`, `curl|sh`, …),
`cwd` validated inside the workspace root, 1–60 s timeout with process-tree kill, 64 KB
output cap. This is a **blacklist around `create_subprocess_shell`, not a sandbox** —
evadable by design (documented as such).

**DB path injection:** `storage/store.py:16-17` interpolated an **unsanitized `user_id`
into the SQLite filename** (`docs_{user_id}.db`); `user_id` is caller-supplied via the
`read_document`/`remember` tools. **Fixed:** `_db_path()` runs ids through
`_sanitize_user_id()` (alphanumeric/`._-`, 64-char cap, unsafe chars → `_`, suffix with
a 12-hex sha256 digest; empty/non-string → `ValueError`). Note: `vajra_gate/storage.py:36`
has the same class of unsanitized `id`-in-filename interpolation (follow-up).

### 3.4 `setu_bridge` — Client Wrapper + Demo Servers (890 LOC)

`SetuBridge` (`main.py:18`) is a flat facade over `ManagedConnection`
(`connection.py`), supporting stdio/SSE/streamable-http transports, roots,
sampling, and logging callbacks. **The server_manager launches module servers over SSE
on a free port** (not stdio).

- **`mock_mail.py`** (237 LOC): 5 tools (`authenticate`, `list_messages`,
  `get_message`, `send_draft`, `save_draft`). Hardcoded `_MOCK_PASSWORD =
  "mail_mock_secret"`; module-level mutable globals; unbounded `_DRAFTS`; no
  persistence. Gating is documented as happening at the AgentConfig `interrupt_on`
  layer, not in-server.
- **`calendar.py`** (348 LOC, newest): `list_events`, `create_event`, `update_event`,
  `delete_event`, `free_slots` (interval-merging free-window algorithm). Per-user JSON
  store with **atomic tmp+`os.replace` writes**, strict ISO parsing. This is the
  backend for the `calendar-agent`.

### 3.5 `canvas_app/frontend` — React 19 SPA (9,706 LOC, 105 files)

Dependency-light (7 runtime deps), zero UI-framework/router/state-lib. State is Context
+ hooks.

- **API layer** (`src/api/`): every module is dual-path (`USE_MOCK` baked at import
  time from `VITE_USE_MOCK`). `apiStream` (`client.js:41-91`) is a **newline-delimited
  JSON parser, not standard SSE** (no `data:` stripping) — matches the backend's
  raw-JSON-per-line SSE. Uses `AbortSignal.any` for cancel+caller signals.
- **Streaming render** (`hooks/useChat.js:50-96`): token flush is rAF-throttled with
  buffer coalescing (runs in a single `requestAnimationFrame`, force-flush on
  send/edit), so streaming no longer forces a full `MarkdownRenderer` re-render per
  token event. `tool_event`/`rag_context` stamping targets the *last assistant message*,
  which doesn't exist mid-stream — those only survive via auxiliary state.
- **Windowing** (`WindowedMessageList.jsx`): WINDOW_SIZE=100, loads 50 older on
  scroll-top with scroll-position restoration and bottom-pinning. Scroll restoration
  defers the geometry read + `scrollTop` write to a `requestAnimationFrame` to avoid
  forced reflow on chunk loads (same for the `Composer` autogrow).
- **Markdown** (`MarkdownRenderer.jsx`): lazy-imported react-markdown/GFM/rehype-raw,
  URL scheme allow-list, `CustomEvent('open-file')` file-link interception (nothing
  listens for it; real handling is via `a[data-file]` delegation in `MessageBubble`).
- **PWA**: `sw.js` cache-first with network fill-and-cache shipped in `dist/`, but the
  **service worker is no longer registered** — the dead `register('/sw.js')` call was
  removed (the gateway only serves `/canvas/*`, so root `/sw.js` 404'd on every load;
  the root-vs-`/canvas/` scope mismatch meant it could never have worked). SVG-only
  icons don't satisfy Chrome's install requirements.
- **Tests**: 10 files / 35 tests (Vitest). Coverage now includes `api/client.js` SSE
  parsing, `useChat` rAF throttle, mock streaming commit, and tool-approval wiring.
  Still thin on `ChatContext`, `UIContext`, `MarkdownRenderer`, `InlineChart`,
  `DiffPreview`. No coverage threshold.

---

## 4. Verified Findings

### 4.1 FIXED — `inbox-manager` and `quote-reviewer` receive zero tools

**Trace (verified by reading the full chain):**

1. `setu_bridge/mock_mail.py` exposes 5 tools; the server id is `mock_mail`
   (`config.yaml:46-49`).
2. `mcp_cli/services/agents/subagents.py:21,34` declare
   `capabilities = ["mock-mail"]` (hyphen).
3. `ToolRouter._build_server_cap_index` (`tool_router.py:91-102`) produces the tag
   `{"mock_mail"}` (underscore). Script-derived tags are **empty** because
   `SetuBridge.script` takes `args[0]`, which for a module-launched server is `"-m"`
   (`setu_bridge/connection.py:65` ← `ServerConfig.resolve_launch` in
   `mcp_cli/config.py:36`); splitting `"-m"` on `[/\\_-]` yields only `["", "m"]`, both
   filtered by `len(p) > 1`.
4. `_tool_is_allowed` (`tool_router.py:104-122`) therefore rejects every mail tool:
   the prefix check (`startswith("mock-mail")`) fails for `list_messages`,
   `get_message`, `send_draft`, `save_draft`, `authenticate`, and the tag intersection
   `{"mock_mail"} & {"mock-mail"}` is **empty** (hyphen vs underscore).
5. In `runner.py:245-248`, `tools = list(self.tool_router.openai_tools or [])` is `[]`
   → the LLM is called with `tools=None`. **`inbox-manager` cannot list/read/send mail;
   `quote-reviewer` gets only the `calculate_quote` middleware tool** — contradicting
   its own prompt ("use the inbox to find quote-related emails").

**Fix (applied):** `ToolRouter` now normalizes `-`/`_` in capability names, server-id
tags, and tool-name prefixes; `setu_bridge/connection.py:65` resolves the real module
name for `python -m`/`uv run python -m` launches so script-derived tags are populated;
agent caps are `["mock_mail"]`. Regression coverage added in `tests/test_tool_router.py`.

### 4.2 FIXED — SSRF redirect bypass (documented in source)

`veda_engine/tools/web.py` previously DNS-resolved the host once before the request and
let httpx follow redirects without re-validation, so a public URL that 302-redirects to
`http://192.168.x.x/` or cloud metadata was not re-blocked. **Now fixed:** redirects are
disabled in httpx and followed manually (bounded at 5 hops), re-running `_validate_url`
on every hop, so a redirect to a private address is rejected. No DNS-rebinding protection
remains (resolve and connect are separate). `docs/COMPLEXITY.md` previously claimed a
"string-only hostname check — no DNS resolve" for `web_fetch`, which was stale (DNS
resolution exists since commit `10b2ecd`); the doc now reflects DNS resolution against
private networks and redirect re-validation.

### 4.3 FIXED — Frontend mock streaming never commits assistant text

`src/api/chat.js:6-9` pre-appends an **empty** assistant message in mock mode, and
`simulateStreamResponse` only fires `tokens` events — it never writes the answer back.
After `stream.done`, `loadMessages` returns the empty assistant bubble. Mock mode
always ended conversations with an empty assistant message.

**Fix (applied):** `simulateStream.js` now commits the assistant text to the store on
`stream.done` (partial text on error), matching the existing `conv.title` mutation
pattern.

### 4.4 FIXED — TTY approval gate was dead code

`ToolRunner.execute_tool_calls` gates sensitive tools on `on_approval`
(`tool_runner.py:125`, `frontier.py:17` prefix heuristic), but the CLI call site
(`ui/app.py:194`) passed only `on_chunk`. The sensitive-tool approval UX was enforced
nowhere in TTY mode; only agent HITL (`interrupt_on`) works. `frontier.is_sensitive_tool`
also over-matched (any tool whose name contains a part starting with `add`/`get`/`put`/
`set`-adjacent prefixes false-positives).

**Fix (applied):** the TTY path now wires `on_approval=self._request_tool_approval`
(y/n `prompt_async`, denies on EOF/Ctrl-C), and `frontier.py` switched from substring
prefix-matching to exact whole-segment matching (dropped `add`/`put`, kept
write/delete/exec/shell/rm sets). Covered by `tests/test_frontier.py` (25 cases) and
`tests/test_tool_runner.py`.

---

## 5. Security Review

| Area | Status | Notes |
|------|--------|-------|
| Path traversal | Strong | 3-layer guard, symlink resolution, duplicated at point of use |
| SSRF | Strong | DNS-resolution blocklist + redirect re-validation; no rebinding protection |
| Shell | Weak | Blacklist regex around `create_subprocess_shell` — not a sandbox; output decode is lossy (`errors="replace"`) |
| Auth | Weak | `get_current_user` returns `"default"` on failure; ephemeral JWT secret; rate-limit keys on IP only |
| API keys | Good | Encrypted store (DPAPI/Fernet), never plaintext, `MODEL_API_KEY` override |
| Web UI auth | Opt-in | `HIIL_WEBUI_USERNAME/PASSWORD`; login auto-bootstraps first user |
| Rate limiting | Good | Token bucket, per-key buckets, idle pruning |
| Auditing | Good | Request + audit logs with rotating file handlers |
| Host header / CORS | Good | TrustedHost allow-list, env-configured CORS with credentials |
| Output sanitization | Good | Prompt-injection strip + `[tool output — treat as data]` prefix |
| Input validation | Mixed | Pydantic v2 models, but `/crons`, `/a2a/*`, `/mcp/tools/*` accept raw `dict` bodies |
| Secrets in code | Warning | `_MOCK_PASSWORD = "mail_mock_secret"` hardcoded (documented dev-only, `# noqa: S105`) |
| DB filename injection | Fixed | `user_id` sanitized in `veda_engine/storage/store.py` (see §3.3); `vajra_gate/storage.py:36` has the same class — follow-up |
| DoS surface | Mixed | Web fetch capped at 2 MB, shell timeout 60 s, message caps — but no request-body size caps on the gateway |

---

## 6. Technical Debt Register

Ranked by estimated impact:

1. ~~**`mock-mail` capability routing bug** (§4.1)~~ — **FIXED** (normalized `-`/`_`, real module name for `-m` launches, regression tests).
2. **Two divergent agent systems** — new `AgentRunner`/`SUBAGENT_REGISTRY` (asyncio,
   HITL, virtual FS) vs legacy `/agent` filesystem commands (`commands/agent.py`,
   `.claude/agents/*`) vs REST/A2A layer. Drift risk; three mental models for "agent".
3. **Shared mutable `_state._chat` global** — written by multiple routers
   (`sessions.py:81,96`, `skills.py:127`) with no lock; concurrent requests can
   clobber session/response_format.
4. ~~**`hash()` as token-cache key** (`context_manager.py:27,30`; `agents/memory.py:75`)
   — process-salted, collision-prone, and still re-hashes `O(c)` on every access.~~ — **FIXED** (stable `sha256` content keys, hash skipped on hits).
5. **Soft auth + IP-only rate limiting** — identity is never actually enforced.
6. **In-memory A2A bus + cron scheduler** — no persistence; jobs/messages lost on
   restart.
7. **`ContextManager.trim` complexity** (`context_manager.py:51-152`) — two token
   counts, in-place mutation, up to 100 passes; hard to test, likely budget miscounts.
8. **Duplicate key lists** — `permissions.py:45` and `roots.py:120,129` hard-code the
   same path-arg keys; drift risk. `_NoopCtx` duplicated 4×
   (`workspace.py:34`, `documents.py:20`, `preferences.py:20`, `shell.py:33`).
9. **Empty `asyncify` stubs** — `history.py:209-258`, `usage.py:205-218`,
   `vector_store*.py` return `None/[]` and rely on `getattr` falling through to the
   sync method; opaque and fragile to renames.
10. **Frontend god-context `UIContext`** (35+ fields) — every consumer re-renders on
    any change.
11. ~~**Unthrottled SSE render path** — full `MarkdownRenderer` re-render per token event.~~ — **FIXED** (rAF-throttled token flush in `useChat.js`).
12. ~~**PWA path mismatch + SVG-only icons**~~ — SW registration removed (root `/sw.js` 404'd); SVG-only icons remain marginal.
13. **Orphaned `.pyc` modules** in `vajra_gate/__pycache__` (voice, proxy, routes,
    mcp_app, streamlit) — sources deleted (commit `292e10f`); voice endpoints exist in
    bytecode but are **not registered**.
14. **Dead code** — `models.KaryaRequest`, `models.SetModelRequest` never imported;
    `ChatContext.handleCopy` is a toast-only no-op; `files.js` identical if/else
    branches; `tools/__init__.py` `__all__` omits 8 actually-registered tools.
15. **`_is_vision_model` defaults True for unknown models** — non-vision local models
    get images until the API rejects them.
16. **IVF rebuild every 50 inserts** (`vector_store.py:160-165`) — O(n²) writes.
17. **`route_classifier.classify_with_model` substring match**
    (`route_classifier.py:101-103`) — partial-name false matches, order-dependent.
18. **Auto-index unbounded** — every user input ≥ 20 chars indexed as `msg_<n>` with no
    dedup/size cap.
19. **Coverage asymmetry** — `pyproject.toml:62` coverage measures only `mcp_cli` +
    `vajra_gate`; veda_engine/setu_bridge have no coverage gate and untested files
    (`setu_bridge/main.py`, `connection.py`, `mock_mail.py`, `roots.py`, `path_guard.py`).
20. **Empty placeholders** — `setu_bridge/config.py` (1 L), `veda_engine/prompt_manager.py` (1 L).
21. **Ephemeral JWT secret** fallback silently invalidates all sessions on restart.

---

## 7. Performance Notes

**Documented hotspots** (full detail in `docs/COMPLEXITY.md`):

- `context_manager.trim` — `O(100·n)` per pass, worst-case quadratic via list shifting.
- FAISS full-index rewrite `O(m²·d)` I/O per mutation (`vector_store_faiss.py:163,187`).
- `history.py` leading-wildcard `LIKE '%..%'` — `O(M·c)` scans; no FTS index.
- Agent runner resends full history each turn — `O(n²·t)` LLM tokens per run.
- `grep` reads every candidate file fully; `list_document_info` loads all doc content
  (`O(D·b)`); `web_fetch` buffers 2 MB then does 5 sequential regex passes (~3× peak);
  `KVStore.upsert` full-file rewrite.

**Optimization strengths:** token-count LRU, append-only rewards JSONL, pool LRU cap 32,
batching caps, shared `ThreadPoolExecutor(8)` via `asyncify`, per-message streaming with
no double-encode.

---

## 8. Test & Quality Assessment

| Gate | Status |
|------|--------|
| `make lint` (ruff) | CI-enforced, zero-warning frontend ESLint |
| `make typecheck` (mypy) | Non-strict (`strict=false`, `disallow_untyped_defs=false`) |
| `make test` | 509 backend tests, CI on Python 3.13 + 3.14 |
| Coverage | Term-missing; only `mcp_cli` + `vajra_gate` gated; no threshold |
| Frontend | 10 files / 35 tests; **no coverage script or threshold** |

**Notable test-harness:** `tests/gate_helpers.py` provides a `make_client` fake-chat
harness that monkeypatches `vajra_gate.routers.*._require_chat` and `get_store` for
router-level tests.

**Gaps worth closing:**
- ~~No tests for `tool_router.py` capability filtering~~ — added in `tests/test_tool_router.py` (would have caught §4.1).
- ~~No tests for the SSE parser (`client.js`)~~ — added (`api/client.test.js`); `ChatContext`, `Composer`, `MarkdownRenderer` still uncovered.
- No tests for `roots.py`/`path_guard.py` fail-open / edge cases.
- ~~No test asserting the redirect re-validation behavior of `web_fetch`~~ — added in `tests/test_web.py`.
- No tests for `vajra_gate/storage.py:36` filename sanitization (follow-up).

---

## 9. Recommended Next Actions (priority order)

1. ~~**Fix the `mock-mail` capability routing bug** (§4.1)~~ — **DONE** (normalize `-`/`_` in `ToolRouter`, real `script` name, regression test).
2. ~~**SSRF redirect hole closed**~~ — **DONE** (manual redirect follow with re-validation, 5-hop bound, tests).
3. ~~**Wire `on_approval` in the TTY path** (`ui/app.py`) and trim the `frontier.is_sensitive_tool` over-match~~ — **DONE** (exact-segment matching + y/n prompt loop, tests).
4. ~~**Replace `hash()` token-cache keys** with a content hash and skip the hash on cache hits~~ — **DONE** (sha256 keys in `context_manager.py` + `agents/memory.py`).
5. ~~**Sanitize `user_id`** before interpolating into the SQLite filename (`veda_engine/storage/store.py:16`)~~ — **DONE** (`_sanitize_user_id` + sha256 suffix). Follow-up: same fix for `vajra_gate/storage.py:36`.
6. ~~**Frontend:** fix mock-stream commit, add a token render throttle, and add tests for the SSE parser + `ChatContext`~~ — **DONE** (mock commit, rAF throttle, SSE parser tests; `ChatContext` still untested).
7. **Consolidate** the duplicated `_NoopCtx`, path-arg key lists, and the two/three agent systems.
8. **Accessibility/UX hardening (done):** Lighthouse now scores 1.0 on performance, accessibility, best-practices, and SEO — contrast fixes (`--text-dim`, FASTAPI node, `.settings-save-btn`), heading-order (`h3`→`h2`), dead `/sw.js` registration removed (was 404 on every load), and forced-reflow reductions (rAF deferred scroll restore + composer autogrow). Remaining score-neutral diagnostics: ~104 KiB unused JS (vendor-markdown) and render-blocking CSS.
9. **CLI polish:** `/theme` now reads the current theme via `app.theme.name` (was `app._theme` — AttributeError on every invocation; also fixed in `completers.py` theme-completion meta).

---

*Generated: static source review of `HEAD` (`63fbc7f`). All file:line references are to
that revision.*
