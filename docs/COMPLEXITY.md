# Space & Time Complexity Analysis — H.I.I.L.

Reference document capturing the complexity analysis of the four main packages:
`mcp_cli`, `vajra_gate`, `veda_engine`, and `setu_bridge`.

## Notation

| Symbol | Meaning |
|--------|---------|
| `n` | messages / items in a collection |
| `T` | total tokens |
| `c` | total characters |
| `m` | rows / vectors |
| `d` | embedding dimension |
| `k` | candidates / tool calls |
| `b` | file bytes |
| `r` | reward events |
| `e` | streamed events |
| `f` | files |

---

## 1. mcp_cli core (`services/`)

| Module | Complexity |
|--------|-----------|
| `chat.py send()` | Space `O(T)` for `chat.messages`; agent dict unbounded |
| `context_manager.trim` | `O(n·T)` re-tokenization, up to 2× per iteration |
| `vector_store.py` | Brute-force search `O(m·d)` pure Python per user message |
| `vector_store_faiss.py` | `_rebuild_index` `O(m²·d)` full rebuild per write |
| `rag.py` | — |
| `history.py` | — |
| `usage.py` | — |
| `chunker.py` | — |
| `streamer.py` | — |
| `tool_router.py` | — |
| `tool_runner.py` | — |
| `verifier/`, `moderation/`, `document_injector` | `@all` pulls all docs into one turn `O(Σ docs)` |

**Space notes:** `chat.messages` is `O(T)`; agent dict unbounded; auto-index
namespace grows forever.

---

## 2. Agent runtime + UI + CLI

| Module | Key complexity |
|--------|---------------|
| `agents/runner.py` | `O(n²·t)` LLM tokens per run — full history resent each turn |
| `agents/runner.py persist` | `_persist_memory` `O(p·(fsize + m·c))` |
| `agents/runner.py archive` | `_summarized_archive` unbounded `O(r·m)` |
| `agents/backend.py` | `_handle_list_directory` `O(f·(d+len))`; search `O(f·lenpat+R)` |
| `agents/code_interpreter.py` | `O(c)` + subprocess spawn per call (~50–200 ms) |
| `agents/permissions.py` | `O((K+A)·P·pats·len)` per tool call |
| `agents/memory.py` | `snapshot_hashes` `O(p·fsize)` re-reads disk every call |
| `ui/history_manager.py` | search loads every session fully `O(S·m+c)` + lowercase copies |
| `ui/completers.py` | per-keystroke `list_sessions()` → `O(N log N)` DB GROUP BY |
| `ui/renderer.py` | `render_inline` 7 regex passes per streaming token; lazy `.*?` worst `O(n²)` |
| `ui/messaging.py`, `tool_events.py` | `result.lower()` twice on multi-MB tool results |
| `ui/codeblock.py` | `O(L·buf)` string slicing; re-wrap + re-parse in `_render_block` |
| `commands/*` | all `O(k)`–`O(m)` |

---

## 3. vajra_gate

| Module | Key complexity |
|--------|---------------|
| `services/reward.py` | `O(r²)` total persistence |
| `chat.py` streaming | `O(e²)` bytes |
| `routers/phase_c.py` ws | `O(e²)` + unbounded `ensure_future` per token |
| `services/store.py` | upsert `O(N_ns)` full-file rewrite; search `O(N_ns·…)` |
| `services/filesystem.py` | `build_tree` `O(f log b)` + symlink-cycle non-termination |
| `routers/search.py` | N+1: loads every matched conversation in full for a title |
| `routers/langgraph.py` | `list_threads` N+1 full loads for `len(msgs)`; fallback search `O(Σ…)` |
| `services/rate_limiter.py` | `O(1)` per check but `_buckets` unbounded (per-IP keys, no TTL) |
| `a2a.py` | `get_messages`/`mark_read` `O(mₐ)` scans; messages never pruned |
| `crons.py` | `_tick` `O(n + Σ M_due + LLM)` serial |
| `metrics.py` | `O(k log k)` generate; unbounded path cardinality |
| `chat_pool.py` | `O(1)` LRU, hard cap 32 — **good** |
| `middleware/logging.py` | sync file writes per request (2 for mutating) |
| `chat.py lekh_record` | `file.flush()` per SSE event |

---

## 4. veda_engine + setu_bridge

| Module | Key complexity |
|--------|---------------|
| `tools/workspace.py _walk_files` | `O(n+d)` full-tree walk on **every** query |
| `tools/workspace.py grep` | `O(n·filesize)`, peak `O(n+b_max)` |
| `tools/workspace.py read_text` | `O(b)` unbounded RAM + payload |
| `storage/store.py list_document_info` | `O(D·b̄)` — fetches full content of every doc |
| `storage/store.py edit` | read `O(b)` → replace `O(b)` → rewrite `O(b)`; peak `2b` |
| `tools/web.py web_fetch` | buffers whole page `O(B)` + 5 sequential `O(B)` passes → peak ~`3×B` |
| `tools/web.py SSRF` | string-only hostname check — no DNS resolve |
| `tools/path_guard.py` | ~3× redundant symlink walks (`resolve`×2 + `realpath`) per check |
| `setu_bridge/mock_mail.py` | `get_message` `O(G)` copy+scan; `_DRAFTS` unbounded; `list_messages` full `O(G)` + `json.dumps` whole mailbox |
| `setu_bridge/connection.py` | no reconnect/backoff despite docstring; cleanup swallows `BaseException` |

---

## Global worst offenders (ranked)

1. `vector_store_faiss._rebuild_index` — `O(m²·d)` full rebuild per write (`vector_store_faiss.py:89,118,128`)
2. Agent loop full-history resend — `O(n²·t)` LLM tokens per run (`runner.py:253`)
3. Reward persistence — `O(r²)` full-file rewrite per event on the event loop (`reward.py:401` → `store.py:61`)
4. Quadratic SSE reply building — `O(e²)` in 3 places (`chat.py:44`, `phase_c.py:77`, `langgraph.py:184`)
5. `ContextManager.trim` re-tokenization — `O(n·T)` ×100 up to 2×/iteration (`context_manager.py:34,62`)
6. `VectorStore` brute-force search — `O(m·d)` pure-Python per user message
7. `_walk_files` full-tree walk per query + unbounded grep (`workspace.py:30,95`)
8. N+1 full-thread loads for trivial metadata (`search.py:21`, `langgraph.py:87`)
9. Unbounded in-memory registries — rate-limit buckets, A2A messages, store cache, metrics paths (4 leak vectors)
10. Full-table scans with missing indexes — `history.search`, `usage.session_summary`, `LIKE '%..%'`

---

## Quick-win fixes (biggest ROI)

- **Indexes:** `CREATE INDEX` on `usage_log(session_id)`, `history(timestamp)`
- **Streaming:** collect chunks in a list, `''.join` once, push only the delta
- **FAISS:** use `add_with_ids`/`remove_ids` instead of rebuilds; vectorize cosine with numpy
- **Rewards:** append-only log / real DB instead of whole-file rewrite
- **Filesystem walks:** `os.walk(followlinks=False)` + `realpath` visited-set; skip `.git`/`node_modules`; apply depth pre-filter
- **Caches:** TTL/eviction for rate buckets, A2A messages, memory snapshots (mtime-based)
