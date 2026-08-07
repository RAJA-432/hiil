# Space & Time Complexity Analysis — H.I.I.L.

Reference document capturing the current (post-optimization) complexity analysis of the
four main packages: `mcp_cli`, `vajra_gate`, `veda_engine`, and `setu_bridge`.

> **Status:** this document reflects the codebase *after* the optimization sweep
> (FAISS deltas, SSE dedup, append-only rewards, token cache, batching caps, eviction).
> Earlier quadratic behaviors are marked FIXED with the change that removed them.
> `FIXED` items no longer warrant work; the ranked **remaining hotspots** at the end
> are the active candidates.

## Notation

| Symbol | Meaning |
|--------|---------|
| `n` | messages / items in a collection |
| `T` | total tokens |
| `c` | total characters |
| `m` | vectors / rows |
| `d` | embedding dimension |
| `k` | candidates / tool calls |
| `b` | file bytes |
| `r` | reward events |
| `e` | streamed events |
| `f` | files |
| `B` | web response bytes |
| `S` | sessions |
| `M` | history table rows |

---

## 1. mcp_cli core (`services/`)

| Module | Complexity |
|--------|-----------|
| `chat.py send()` | Space `O(T)` for `chat.messages`; agent dict bounded by pool cap 32 |
| `context_manager._token_cache` | `O(1)` memo lookup, but `O(c)` content hash on **every** access even on hits |
| `context_manager.trim` | **Hotspot:** `O(100·n)` per pass, O(n²) worst via `insert(0)`/`pop(1)` shifts (`:94-145`) |
| `vector_store_faiss.py` | `add_with_ids`/`remove_ids` + numpy `matrix @ query` — `O(m·d)` per search. **Hotspot:** full index write `O(m²·d)` I/O per mutation (`:163,:187`) |
| `vector_store.py` | Brute-force pure-Python `O(m·d)` per user message (legacy fallback backend) |
| `rag.py` | chunks m vectors; concurrent FAISS ingest amplifies the per-write index I/O |
| `history.py` | **Hotspot:** leading-wildcard `LIKE '%..%'` scans `O(M·c)` (`:133,:167`); no FTS index |
| `usage.py` | indexed on `session_id` — FIXED |
| `chunker.py`, `streamer.py` | `O(c)` linear |
| `tool_router.py` | route match `O(k)`; sub-agent path covered by discovery guard |
| `tool_runner.py` | `O(1)` registry lookup per call |
| `verifier/`, `moderation/`, `document_injector` | `@all` pulls all docs into one turn `O(Σ docs)` |

**Space notes:** `chat.messages` is `O(T)`; pool LRU capped at 32 (FIXED). `_summarized_archive`
in the agent runner remains unbounded by design (audit log) — see below.

---

## 2. Agent runtime + UI + CLI

| Module | Key complexity |
|--------|---------------|
| `agents/runner.py` | `O(n²·t)` LLM tokens per run — full history resent each turn (`:253`); `_summarized_archive.extend()` unbounded `O(r·m)` (`:302`) |
| `agents/runner.py persist` | `_persist_memory` `O(p·(fsize + m·c))` substring scan per file |
| `agents/backend.py` | `_handle_list_directory` `O(f·(d+len))`; search `O(f·lenpat+R)` |
| `agents/code_interpreter.py` | `O(c)` + subprocess spawn per call (~50–200 ms) |
| `agents/permissions.py` | `O((K+A)·P·pats·len)` per tool call |
| `agents/memory.py` | snapshot hashes re-read disk every call; mtime cache added — partially FIXED |
| `ui/history_manager.py` | **Hotspot:** `/search` loads every session fully `O(S·M)` (`:130`) |
| `ui/completers.py` | per-keystroke `list_sessions()` → `O(N log N)` DB GROUP BY |
| `ui/streaming.py` | delta-only render + throttle — FIXED |
| `ui/messaging.py`, `tool_events.py` | `result.lower()` twice on multi-MB tool results |
| `ui/codeblock.py` | `O(L·buf)` string slicing; re-wrap + re-parse in `_render_block` |
| `commands/*` | all `O(k)`–`O(m)` |

---

## 3. vajra_gate

| Module | Key complexity |
|--------|---------------|
| `services/reward.py` | append-only JSONL persist `O(1)` per event — **FIXED** (was `O(r²)`) |
| `services/reward.py` reads | **Hotspot:** `O(r log r)` sort before limit + `O(r)` persistent in-RAM cache (`store.py:94,:133`) |
| `chat.py` streaming | delta-only SSE, single join — **FIXED** `O(e)` (was `O(e²)`) |
| `routers/phase_c.py` ws | delta-only + bounded per-token tasks — **FIXED** (was `O(e²)`) |
| `services/store.py` | **Hotspot:** non-reward namespaces (preferences, langgraph) still full-file rewrite `O(N_ns)` per upsert (`:68,:122`) |
| `services/filesystem.py` | `followlinks=False` + realpath visited-set + depth/noise-dir prune — **FIXED**; `build_tree` sort-key `isdir` does double syscalls (watch) |
| `routers/search.py` | metadata-only summaries — **FIXED** N+1 (was full thread loads for a title) |
| `routers/langgraph.py` | `list_threads` metadata-only + indexed fallback — **FIXED** N+1 |
| `services/rate_limiter.py` | `O(1)` per check + TTL `prune_idle` — **FIXED** unbounded buckets |
| `a2a.py` | messages pruned at 10k cap — **FIXED**; **watch:** `_agents` registry never evicted (`:79`) |
| `crons.py` | `_tick` `O(n + Σ M_due + LLM)` serial; `_jobs` pruned — **FIXED** |
| `metrics.py` | `O(k log k)` generate; path cardinality capped at 1000 `"other"` — **FIXED** |
| `chat_pool.py` | `O(1)` LRU, hard cap 32 — **good** |
| `middleware/logging.py` | sync file writes per request (2 for mutating) |
| `chat.py lekh_record` | `file.flush()` per SSE event |

---

## 4. veda_engine + setu_bridge

| Module | Key complexity |
|--------|---------------|
| `tools/workspace.py _walk_files` | full-tree walk `O(n+d)` per query, but depth-capped (4) + noise-dir skip — partially FIXED |
| `tools/workspace.py grep` | **Hotspot:** `O(n·b)` sequential full-file reads, no byte cap, user regex → ReDoS risk (`:116-127`) |
| `tools/workspace.py read_text` | hard-capped at `_MAX_FILE_BYTES` (100KB) — **FIXED** |
| `tools/workspace.py read_text_batch` | 20 files / 100KB each / 500KB total cap — **FIXED** |
| `tools/web.py web_fetch` | streamed + DNS-resolve SSRF + redirect re-validation + 2MB hard cap — **FIXED** (was `O(B)`×5 passes ~3×B) |
| `tools/shell.py` | timeout capped 60s, chunked reads — **FIXED** |
| `storage/store.py` | **Hotspot:** new SQLite conn per call (`:20-32`); `list_document_info` loads all content `O(D·b̄)` (`:110-115`) |
| `storage/store.py edit` | read `O(b)` → replace `O(b)` → rewrite `O(b)`; peak `2b` |
| `tools/path_guard.py` | ~3× redundant symlink walks (`resolve`×2 + `realpath`) per check |
| `setu_bridge/calendar.py` | **Hotspot:** full JSON rewrite `O(E)` per mutation; all events in RAM forever (`:57-99`) |
| `setu_bridge/mock_mail.py` | `get_message` `O(G)` copy+scan; `_DRAFTS` unbounded; `list_messages` full `O(G)` + `json.dumps` whole mailbox |
| `setu_bridge/connection.py` | no reconnect/backoff despite docstring; cleanup swallows `BaseException` |

---

## FIXED (verified in current code) ✅

| Fix | Complexity change | Evidence |
|---|---|---|
| SSE/WS streaming | `O(e²)` → `O(e)` delta + single join | chat.py, phase_c.py, langgraph.py |
| FAISS writes | `O(m²·d)` rebuild → `add_with_ids`/`remove_ids` + numpy search | vector_store_faiss.py:134,158-159,180 |
| Reward persist | `O(r²)` → `O(1)` append-only JSONL | reward.py:372 |
| Trim tokenization | re-tokenize → `_token_cache` memo | context_manager.py:21-41 |
| Indexes | `session_id` + `timestamp` | history, usage |
| Filesystem walks | `followlinks=False` + visited-set + depth/noise prune | workspace.py:41-47 |
| `web_fetch` | `O(B)`×3 → 2MB streamed cap + DNS-resolve SSRF + redirect re-validation | web.py:64,70,123 |
| `read_text` / `read_text_batch` | 100KB / (20×100KB, 500KB total) caps | workspace.py:19-21,212-216 |
| N+1 threads | metadata-only summaries | search.py, langgraph.py |
| Rate limiter | TTL prune, `O(1)` check | rate_limiter.py:46,54 |
| A2A messages | 10k hard cap + prune | a2a.py:59,112-116 |
| Metrics cardinality | 1000-path `"other"` bucket | metrics.py |
| Chat pool | `O(1)` LRU, cap 32 | chat_pool.py |
| Shell tool | 60s timeout, chunked reads | shell.py:14,49 |
| Crons | `_jobs` pruned | crons.py:62 |

---

## Remaining hotspots (ranked)

1. **`vector_store_faiss` full index write per mutation — `O(m²·d)` I/O** (`:163` every insert, `:187` every delete).
   Deltas in memory are O(m·d), but each op writes the whole index to disk; `rag.py` ingests m chunks concurrently → quadratic disk I/O on the hot path.
2. **`context_manager.trim` — `O(100·n)` with O(n²) worst list shifts** (`:94-145`). `max()` over tail, `json.dumps` biggest msg, `insert(0)`/`pop(1)` shifts — up to 100× per pass, ×2 per send ×10. Token cache doesn't help; the structure does.
3. **KVStore non-reward upsert — `O(N_ns)` full-file rewrite per write** (`store.py:68,:122`). Preferences + langgraph `store_upsert` rewrite the whole namespace JSON per change — same quadratic the rewards log was fixed to avoid.
4. **History search — leading-wildcard `LIKE '%..%'` → `O(M·c)` full scans** (`history.py:133,:167`), plus UI `/search` load-all `O(S·M)` (`history_manager.py:130`). No FTS index.
5. **Reward read path — `O(r log r)` sort before limit + `O(r)` persistent in-RAM cache** (`store.py:94,:133`). Writes fixed; reads still materialize all events.
6. **A2A registry — `_agents` never evicted** (`a2a.py:79`); `get_messages`/`mark_read` still `O(m)`/`O(m log m)` full-list scans (`:129-142`).
7. **`veda_engine` grep — `O(n·b)` sequential full-file reads, no byte cap, user regex → ReDoS** (`workspace.py:116-127`).
8. **Calendar store — `O(E)` full JSON rewrite per mutation + all events in RAM forever** (`calendar.py:57-99`).
9. **Document store — new SQLite conn per call (`store.py:20-32`) + `list_document_info` loads all content `O(D·b̄)`** (`:110-115`).
10. **Runner/archive — `_summarized_archive.extend()` unbounded `O(r·m)`** (`runner.py:302`); `_persist_memory` O(n·c) substring scan per file.

---

## Watch-list (low severity)

- `mock_mail._DRAFTS` unbounded; `list_messages` full `O(G)` + `json.dumps` whole mailbox.
- `filesystem.build_tree` `isdir` inside sort key → double syscalls per node.
- `claude.py` theoretical `O(len²)` argument concatenation.
- `setu_bridge/connection.py` swallows `BaseException` in cleanup; no reconnect/backoff.
- `context_manager._token_cache` hashes content `O(c)` on every call even on cache hits.

---

## Space summary

- **Bounded (FIXED):** chat pool (32), rate-limit buckets (TTL), A2A messages (10k), metrics paths (1000), crons jobs, FAISS per-namespace.
- **Unbounded:** reward in-memory cache `O(r)`, `_summarized_archive`, mock-mail `_DRAFTS`, calendar `_data`, A2A `_agents`.

---

## Suggested next work (biggest ROI)

1. **FAISS write batching** — coalesce concurrent inserts/deletes into periodic full writes (or per-namespace shard files) to kill the `O(m²·d)` I/O.
2. **`ContextManager.trim` rewrite** — drop `insert(0)`/`pop(1)` (use index offsets / a single retained list + slice) to reach `O(n)`.
3. **KVStore append-style namespaces** — reuse the JSONL append pattern from rewards for preferences/langgraph.
4. **History FTS** — FTS5 table or suffix-constrained index for `LIKE`; stop loading all sessions in `/search`.
5. **grep hardening** — byte cap per file + bounded total, precompile regex with timeout, skip binary files.
