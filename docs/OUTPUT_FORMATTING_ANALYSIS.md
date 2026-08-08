# H.I.I.L. — Output Formatting & Streaming Analysis

Complete technical review of how model output is produced, transported, and rendered in
the H.I.I.L. codebase: the `NotificationBus` event protocol, the HTTP streaming wire
format (chat / agents / langgraph routes), the CLI ANSI renderer, and structured-output
(`response_format`) enforcement.

> **Scope note:** static code review (source read + verified traces), not a runtime load
> test. File/line references point at `HEAD`; line numbers may drift. Commit reviewed:
> current working tree.

---

## 1. Executive Summary

Output flows through four distinct layers:

| Layer | Mechanism | Key files |
|-------|-----------|-----------|
| Producer | LLM turn → streamed events | `mcp_cli/services/session/turn_pipeline.py` |
| Transport | Async pub-sub bus → NDJSON lines over HTTP | `mcp_cli/services/notification_bus.py`, `vajra_gate/chat.py` |
| Consumer (web) | Fetch + line-split JSON parser, React state | `canvas_app/frontend/src/api/client.js`, `hooks/useChat.js` |
| Consumer (CLI) | Markdown → ANSI, throttled streaming | `mcp_cli/ui/renderer.py`, `messaging.py`, `streaming.py`, `codeblock.py` |
| Enforcement | `response_format` JSON-schema + retry/recovery | `mcp_cli/services/chat.py`, `session/turn_pipeline.py`, `session/recovery.py` |

**Verdict:** the design is sound for a self-contained full-stack app — one async bus per
request, one JSON object per line, and a clean split where the CLI consumes tokens via a
direct callback (never over the bus) while the web consumes the bus over HTTP. The main
risks are correctness/robustness, not architecture:

- **F1 (high):** a subscription race in `vajra_gate/chat.py` can silently drop early
  events from the JSONL audit log and the reward tracker.
- **F2 (medium):** the wire format is NDJSON mislabeled as `text/event-stream`, and is
  not real SSE.
- **F3 (medium):** the three streaming routes use three different event envelopes, so no
  client can share a parser.
- **F4 (medium):** queue/buffer-full drops events silently, including `tokens` — reply
  content can be truncated under load.
- **F5 (low):** per-request task overhead (chat + heartbeat + log + reward = 4 tasks per
  stream) and a dead `push_metric` code path.

---

## 2. Output pipeline overview

```
LLM stream chunk ──► on_chunk ──► NotificationBus ──► SSE/NDJSON ──► React SPA
                    (turn_pipeline)      │
                                         ├─► CLI: consumed via on_chunk callback (no bus)
                                         ├─► JSONL audit log (VAJRA_GATE_CHAT_LOG)
                                         └─► reward tracker observer

LLM final reply ──► _finalize_output (verifier + moderation) ──► "done" event
```

One `NotificationBus` instance is created **per request** (`vajra_gate/chat.py:42`,
`routers/langgraph.py:183`, `routers/agents.py:83`) and fans out to every subscriber.

---

## 3. Layer 1 — the `NotificationBus` event protocol

`mcp_cli/services/notification_bus.py` is an async broadcast hub. Key semantics:

- **Seq ordering:** every broadcast increments `_seq` and stamps `event["seq"]`
  (`notification_bus.py:33-34`). Clients can order events and detect gaps.
- **Pre-subscriber buffering:** events published before any subscriber registers are
  buffered (cap 1000) and replayed to the **first** subscriber that registers
  (`notification_bus.py:27-28, 102-105`). After that the buffer is cleared.
- **Termination:** producers call `push_done()`; each subscriber loop breaks on
  `{"type": "done"}` (`notification_bus.py:116-117`).
- **Backpressure:** none for tokens. `_broadcast` uses `put_nowait` and drops on a full
  subscriber queue (cap 1000) (`notification_bus.py:42-45`).

### 3.1 Event inventory

| `type` | Producer | Payload | Consumers |
|--------|----------|---------|-----------|
| `tokens` | `push_tokens_nowait` via `on_chunk` (`chat.py:44-45`) | `text` (partial reply) | SPA `useChat.js:84`; reward observer (`chat.py:116-124`); JSONL log |
| `tool_event` | `push_tool_call_nowait` (`chat.py:47-48`) | `tool`, `status`, `args`, `result` (≤200 chars) | SPA `useChat.js:87`; reward observer (`chat.py:105-115`); JSONL log |
| `rag_context` | `push_rag` (`turn_pipeline.py:111`) | `chunks` | SPA `useChat.js:103`; JSONL log |
| `log` | `push_log` (throughout `turn_pipeline.py`) | `level`, `text`, `source` | SPA `useChat.js:116`; CLI spinner status (`turn_renderer.py:78-80`); JSONL log |
| `state` | `push_state` (`turn_pipeline.py:131,222,…`) | `phase`, `agent_id`, `timestamp`, `iteration` | SPA `useChat.js:119`; CLI phase report (`turn_renderer.py:84`); JSONL log |
| `progress` | `push_progress` | `current`, `total`, `percent`, `text` | defined, not consumed anywhere in SPA/CLI |
| `interrupt` | `push_interrupt` (`routers/agents.py:93`) | `action_requests` | SPA `useAgents.js:39`, `AgentRunModal.jsx:100` |
| `heartbeat` | `_heartbeat` (`chat.py:88-94`, 5 s) | `timestamp` | no consumer filters it (ignored by fall-through) |
| `done` | `push_done` | — | all subscribers terminate |

### 3.2 Findings (Layer 1)

- **F1 — subscription race (high).** In `_merge_events` (`vajra_gate/chat.py:145-148`)
  the chat task is created *before* the log, heartbeat, and reward tasks, and the SSE
  subscriber registers at `bus.events()` (`chat.py:151`). Events pushed by the chat
  before `lekh_record`/`_reward_observer` subscribe are buffered, replayed to the first
  subscriber (SSE) only, then the buffer is cleared (`notification_bus.py:103-105`).
  Consequence: the JSONL audit log (`VAJRA_GATE_CHAT_LOG`) and the reward tracker can
  silently miss the RAG-context push, early `log` events, and the first `tokens` of a
  fast reply. The failure is timing-dependent and invisible.
- **F4 — silent drop on backpressure (medium).** `tokens` uses `put_nowait` and is
  dropped if a queue is full (`notification_bus.py:42-45`), and pre-subscriber events
  are dropped if the 1000-event buffer overflows (`notification_bus.py:39`). For chat
  this means reply text can be truncated with only a `logging.warning` that nobody sees.
- **F6 — dead code (low).** `turn_pipeline.py:147-149` guards `push_metric` with
  `hasattr`, but `NotificationBus` has no such method — the branch is unreachable
  (confirmed: only a test stub in `validate_hiil_fix.py:111` defines it).

---

## 4. Layer 2 — HTTP wire format (NDJSON mislabeled as SSE)

All three streaming routes emit `json.dumps(event) + "\n"` and label it
`text/event-stream`:

- Chat: `vajra_gate/chat.py:51` → bare bus event.
- Agents: `vajra_gate/routers/agents.py:105` → bare bus event.
- LangGraph: `vajra_gate/routers/langgraph.py:208` → **wrapped**:
  `{"event": <type>, "data": <bus-event>}`, plus synthetic `metadata`, `complete`, and
  `error` envelope events (`langgraph.py:185, 212, 218`).

### 4.1 Framing safety

`json.dumps` escapes embedded `\n` inside strings, so each event is guaranteed to be a
single physical line — the line-split contract cannot be corrupted by tool output or log
text. This is a genuine strength of the NDJSON choice.

### 4.2 Findings (Layer 2)

- **F2 — not real SSE (medium).** Standard SSE requires `data: <payload>\n\n` with
  optional `event:`/`id:` fields, so that `EventSource` and SSE tooling work. This API
  emits bare JSON lines; `EventSource` would reject it. The media type is therefore
  misleading, and the endpoint is non-interoperable with generic SSE clients/proxies.
  The frontend compensates with a bespoke parser (`client.js:65-86`). Either prefix
  `data:` + blank-line terminator, or advertise `application/x-ndjson`.
- **F3 — inconsistent envelopes (medium).** `/api/chat` and `/api/agents/{id}/run`
  yield bare bus events; `/threads/{id}/runs/stream` wraps them and adds its own
  terminal/error events. A third-party client (or future first-party parser) cannot
  share one decoder. The LangGraph wrapper also nests the bus event's own `type` inside
  `data`, creating a redundant two-level type structure.
- **F8 — heartbeat leaks to all consumers (low).** `_heartbeat` broadcasts into the bus
  (`chat.py:92`), so every 5 s the SPA receives (and ignores) a heartbeat frame and the
  audit log writes one. Harmless but wasted bytes; the SPA `useChat.js` falls through on
  unknown types so it is never surfaced.
- **F7 — truncated tool results (low).** `push_tool_call_nowait` clips `result` to 200
  chars (`notification_bus.py:55,82`). There is no follow-up endpoint to fetch the full
  result, so the SPA's tool-call UI can never show more than a 200-char excerpt.

### 4.3 Non-streaming path

`routers/chat.py:51-58` returns `ChatResponse(reply=…)` when the client does not request
SSE — a clean fallback. The 300 s global timeout (`routers/chat.py:24,55`) applies only
here, not to the streamed path.

---

## 5. Layer 3 — CLI terminal rendering

The CLI deliberately **does not** render from the bus: `TurnRenderer` wires `on_chunk`
straight into the renderer (`mcp_cli/ui/turn_renderer.py:57-68`) and uses the bus only
for status/phase updates (`turn_renderer.py:73-91`, handling `log`, `state`, `done`).

- **`MarkdownRenderer`** (`ui/renderer.py`) converts Markdown → ANSI. Dark/light
  palettes of 24-bit color codes; regex-based inline bold/italic/link/code/image and
  fenced-code blocks rendered as a bordered box with a language badge
  (`renderer.py:137-158`).
- **`CodeBlockAccumulator`** (`ui/codeblock.py`) intercepts fenced blocks mid-stream and
  only emits them once the closing fence arrives, so the terminal never shows an
  in-progress block; unclosed blocks are flushed on stream end.
- **`StreamingRenderer`** (`ui/streaming.py`) throttles inline rendering to one render
  per 50 ms window, coalescing token bursts.
- **`MessageManager`** (`ui/messaging.py`) adds role badges (`👤 You` / `🤖 Assistant`),
  separators, optional timestamps, and truncates tool results to 4 lines with a
  `/expand` hint.
- **`SpinnerManager`** (`ui/messaging.py:158-236`) animates a Braille spinner while
  thinking/tool-calling.

### 5.1 Findings (Layer 3)

- The CLI and web paths are fully separate renderers with separate parsers; a wire-format
  regression cannot be caught by CLI tests. The SPA's `api/client.test.js` is the only
  guard on the NDJSON contract.
- `renderer.py` regexes are order-dependent (image before link etc.) and strip unmatched
  `*`/`**` across chunk boundaries (`renderer.py:124`) — acceptable for streaming, but a
  full markdown parser would be more faithful for the final re-render on complete reply.

---

## 6. Layer 4 — structured output enforcement

- `CliChat` optionally passes `response_format` (`{"type": "json_schema", "json_schema":
  {name, schema}}` or `{"type": "json_object"}`) to the provider
  (`mcp_cli/services/chat.py:423-425`, `claude.py:108-109,170-171`).
- `TurnPipeline` validates the reply against the JSON schema (`turn_pipeline.py:223`);
  on failure it injects a corrective user message and retries, bounded by
  `RecoveryHandler` (`turn_pipeline.py:249-255`, `session/recovery.py`), then falls back
  to returning the raw output (`turn_pipeline.py:257-269`).
- Final answer passes the verifier/critique pass and moderation
  (`turn_pipeline.py:368-378`); usage for the verifier round-trip is recorded
  (`turn_pipeline.py:309-321`).

This layer is well-structured; no findings beyond the `push_metric` dead branch noted
above.

---

## 7. Performance & scalability

| Aspect | Assessment |
|--------|------------|
| Per-chunk cost | One `_broadcast` per LLM chunk; each event is JSON-serialized at publish (bus) and again at the SSE sink (`chat.py:51`). Fine for one stream, ~2× serialization overhead. |
| Per-request tasks | 4 background tasks per stream (chat, 5 s heartbeat, JSONL writer, reward observer) — `chat.py:145-148`. ~3×N idle tasks at N concurrent streams. |
| Frontend render | `useChat.js` buffers tokens and flushes via `requestAnimationFrame` (`useChat.js:84-86`), so the DOM only re-renders once per frame regardless of chunk rate. Good. |
| Queue caps | Hard 1000-event caps on subscriber queues and pre-subscriber buffer; overflow drops data (F4). |
| Audit log | `lekh_record` flushes every 50 lines (`chat.py:70-74`) — bounded write cost. |

---

## 8. Security considerations

- **Framing:** NDJSON is safe from CRLF/header injection because payloads are
  `json.dumps`-escaped and responses go through `SecurityHeadersMiddleware` + the
  trusted-host/CORS allow-lists (README §Security). No raw user text is ever emitted
  unescaped into the stream.
- **Heartbeat injection:** `_heartbeat` writes `timestamp` via `datetime.isoformat()` —
  no attacker-controlled data.
- **Tool results:** clipped to 200 chars on the wire, reducing (not eliminating)
  leakage surface for sensitive tool output; the CLI truncates to 4 lines similarly.
- **Done events:** `push_done` fires even on producer error (`chat.py:141-143`), so a
  client never hangs waiting for a terminal event.

---

## 9. Recommendations (priority order)

| # | Severity | Change |
|---|----------|--------|
| 1 | High | **Fix the subscription race (F1).** In `_merge_events`, create the log/heartbeat/reward subscribers (or register `bus.events()` iterators) before `create_task(run_chat())`, so no event is emitted before every subscriber is attached. |
| 2 | Medium | **Decide the wire contract (F2/F3).** Either switch to real SSE framing (`data:` + blank line) or rename to `application/x-ndjson`; and standardize a single envelope (e.g. always `{"event": <type>, "data": …}`) across `/api/chat`, `/api/agents/{id}/run`, and `/threads/{id}/runs/stream`, reusing one parser in `client.js`. |
| 3 | Medium | **Backpressure for tokens (F4).** Use an async put (await on full queue) for `tokens`/`tool_event` so reply content is never dropped; keep drop semantics only for `log`/`progress`/`heartbeat`. |
| 4 | Low | **Consolidate per-stream tasks (F5).** Fold the 5 s heartbeat into the SSE generator (yield a heartbeat when `asyncio.wait_for` on the queue times out) and make the JSONL writer/reward observer optional or multiplexed, cutting 4 tasks → 1-2 per stream. |
| 5 | Low | **Remove dead code (F6).** Implement `push_metric` on `NotificationBus` or drop the `hasattr` branch in `turn_pipeline.py:147-149`. |
| 6 | Low | **Filter heartbeat from audit log / expose full tool results (F7/F8).** Skip `heartbeat` in `lekh_record`, and add a `GET /api/tools/results/{call_id}` (or increase the clip to a configurable limit) so the SPA can expand tool output. |

---

## 10. Appendix — verified references

- `mcp_cli/services/notification_bus.py` — bus, seq, buffering, drop semantics, all push methods.
- `vajra_gate/chat.py` — `_stream_chat` (NDJSON at line 51), `_merge_events` (task fan-out at 145-148), `_heartbeat` (88-94), `lekh_record` (54-85), `_reward_observer` (97-128).
- `vajra_gate/routers/chat.py` — SSE detection (44-49), non-stream fallback (51-58).
- `vajra_gate/routers/agents.py` — agents stream, bare envelope (105).
- `vajra_gate/routers/langgraph.py` — wrapped envelope (208), `metadata`/`complete`/`error` (185, 212, 218).
- `mcp_cli/services/session/turn_pipeline.py` — event producers, `response_format` validation/retry, `push_metric` dead branch (147-149).
- `canvas_app/frontend/src/api/client.js` — NDJSON line-split parser (41-97); `api/client.test.js` guards the contract.
- `canvas_app/frontend/src/hooks/useChat.js` — event→state mapping (84-122), RAF token flush.
- `mcp_cli/ui/renderer.py`, `ui/messaging.py`, `ui/streaming.py`, `ui/codeblock.py`, `ui/turn_renderer.py` — CLI rendering stack.
- Frontend mock stream: `canvas_app/frontend/src/api/mocks/streams/simulateStream.js` mirrors the event types.
