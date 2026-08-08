# RAG Scaling Runbooks

Practical, bullet-driven runbooks for scaling and operating the hiil RAG stack.
Covers chunking, context-budget fallback, vector-store backends, token
monitoring, and Docker packaging.

> **Note on module provenance.** Some features referenced below are provided by
> modules that may be added in parallel with this document (`token_monitor`,
> `prompt_budget`) and are new modules. If an import is missing in your tree,
> they have not landed yet; everything else (chunker, rag, vector_store,
> usage, eval.*) is already present.

---

## 1. Chunking runbook

### Where to change it
- `mcp_cli/services/chunker.py` — pure chunking functions:
  - `chunk_by_tokens(text, chunk_size=512, overlap=50)` — word-window chunker.
  - `chunk_by_content(text, default_size=512, overlap=50)` — adapts size by content type.
  - `chunk_by_sentences(text, max_chars=1500, overlap_chars=150)` — sentence-boundary chunker.
  - `suggest_chunk_size(text, default=512)` — code chunks get `64..256`, prose keeps the default.
- `mcp_cli/services/rag.py` — `index_document(..., chunk_size=None, chunk_overlap=50)`; `None` size routes through `chunk_by_content`.

### How to change chunk size / overlap
- Pass `chunk_size` and `chunk_overlap` into `RagPipeline.index_document(...)` for a per-ingest override.
- To change the default for the whole pipeline, edit the `default_size=512` / `overlap=50` defaults in `chunker.py` and the `default_size=512, overlap=chunk_overlap` call in `rag.py`.

### Dynamic content-type sizing
- `detect_content_type(text)` classifies a chunk as `code` or `text` (line-ending heuristics + keyword scan).
- `chunk_by_content` shrinks code chunks automatically so function/class boundaries stay dense for embeddings; prose keeps the larger default window. No per-document tuning needed for mixed corpora.

### The A/B benchmark
- `python -m eval.chunking_bench [--chunk-size 512] [--overlaps 0,50,100]` (hermetic, no LLM).
- Columns: `overlap`, `chunks`, `indexed`, `overhead` (indexed words / source words), `needles`, `preserved`, `preservation`.
- Read it as: higher `preservation` = fewer facts lost at chunk boundaries; higher `overhead` = more duplicate tokens indexed (cost).
- `tests/test_chunking_bench.py` pins the invariants (overlap preserves needles, more overlap ⇒ more redundancy).

### Defaults and why
- `overlap=50` is the measured sweet spot: it reaches 100% needle preservation at the lowest overhead (vs `0` and `100`). Keep it unless your corpus has very long boundary-straddling facts.
- `chunk_size=512` balances embedding density against query relevance; raise for dense prose, lower for code.

---

## 2. Fallback runbook (context budget)

### How the fallback works
- `RagPipeline.retrieve_compressed(query, ..., max_tokens=MAX_CONTEXT_TOKENS)` (`rag.py`) accumulates retrieved chunks in score order until the budget is consumed.
- If a single top hit alone exceeds the budget, `_condense_result` asks the LLM to compress it ("Condense this into the most relevant 300 words…"); if summarization is unavailable or fails it degrades to plain truncation.

### Thresholds
- `MAX_CONTEXT_TOKENS = 3500` is the hard assembly cap (`rag.py:19`).
- Warn / hard **monitoring** thresholds live in `token_monitor.py`:
  - `WARN_THRESHOLD = 3500` — at/above this, `TokenMonitor.record(...)` reports level `warn` and `fallback_action()` = `compress`.
  - `HARD_THRESHOLD = 3800` — at/above this, level `critical` and `fallback_action()` = `truncate`.

### How to adjust `MAX_CONTEXT_TOKENS`
- In code: change the module constant in `rag.py`.
- At runtime: set `MAX_CONTEXT_TOKENS` env var (respected by `mcp_cli/config.py` for the app settings) or `max_context_tokens` in `config.yaml`.
- The `token_monitor` thresholds are constructor args (`TokenMonitor(warn_threshold, hard_threshold)`) and module constants.

### How to test
- `tests/test_token_monitor.py` — level classification, `should_fallback`, `fallback_action` transitions (`ok → compress → truncate`).
- `tests/test_rag.py` — `retrieve_compressed` budget capping and condense/truncate behavior (LLM mocked).
- `python -m eval.token_bench --docs 10 --seed 42` — hermetic A/B of the 206-token vs 4k-token budgets to size your own threshold.

---

## 3. Vector DB runbook

### Backends
- `mcp_cli/services/vector_store.py` — `VectorStore` (sqlite + optional in-process IVF). Default, zero extra deps.
- `mcp_cli/services/vector_store_faiss.py` — `FaissVectorBackend` (needs `faiss` + `numpy`; not in `pyproject.toml` deps — install explicitly). Auto-fallback in `create_vector_store` when faiss is missing.
- `create_vector_store(backend="sqlite"|"faiss", db_path=None)` — factory used by `mcp_cli/services/factory.py:102` (backend driven by the `vector_backend` config setting).
- Default `db_path` = `Path.home() / ".hiil" / "vectors.db"` (sqlite store lives there too; faiss adds a `faiss_index/` directory beside it).

### IVF tuning knobs
- `IVFIndex(n_clusters=32, n_probe=4, min_vectors_for_cluster=100)` (`vector_store.py`).
- Larger `n_clusters` → finer partitions (faster search, more rebuild cost); larger `n_probe` → better recall, slower queries.
- IVF only engages once a namespace holds enough vectors (`>= min_vectors_for_cluster`, and only when numpy is importable); otherwise `search` falls back to a brute-force cosine scan.
- Note: the IVF centroid build uses a fresh `default_rng()` per rebuild, so results are not deterministic across runs.

### Disk persistence & hybrid search
- sqlite persists vectors/metadata in the `.db` file; WAL mode (`journal_mode=WAL`) is enabled by `SqliteStore`.
- faiss persists the index per-namespace as `faiss_index/<namespace>.index` and re-loads on startup; delete/rebuild are transparent.
- Hybrid search: `retrieve` + metadata filtering — `RagPipeline.retrieve_scoped(query, filters, ...)` restricts chunks to those whose metadata matches every key/value pair (exact-match filter on top of vector similarity).

### When to move to Chroma
- When corpora outgrow a single sqlite file (tens of thousands of chunks), you need horizontal scaling, or you want hosted persistence.
- `docker compose --profile vector-db up -d` brings up `chromadb/chroma:latest` (commented/optional — never required for default operation). Point the app at it via the vector backend settings.
- Budgets first: run `python -m eval.token_bench` and `python -m eval.chunking_bench` — most deployments hit context/token limits before index scale.

---

## 4. Monitoring runbook

### Reading token usage
- `mcp_cli/services/usage.py`:
  - `count_tokens(text, model)` — tiktoken-backed counter (content-array aware; images = 85 tokens) with `len//4` fallback.
  - `UsageTracker` — sqlite-persisted per-session records (`record`, `session_summary`, `session_summary_for`, `total_summary`, `history`).
  - `estimate_cost(model, input, output)` / `format_cost(...)` — USD + INR pricing per `MODEL_PRICING`.
- `TokenMonitor` (new module) — in-memory per-turn snapshots: `record(in, out, context, session_id)`, `status()`, `should_fallback()`, `fallback_action()`. Aggregates a rolling window (`max_recent=200`) and exposes `warnings` / `critical_hits`.

### Thresholds & alerting hooks
- Levels: `ok` < `warn` (3500) < `critical` (3800). At `warn` → `compress`; at `critical` → `truncate`.
- Raise/lower via `TokenMonitor(warn_threshold=..., hard_threshold=...)` or the module constants in `token_monitor.py`.
- Integrations:
  - **Sentry**: in the alert branch (level `warn`/`critical`), `sentry_sdk.capture_message(...)` with the `status()` dict as extra context.
  - **Grafana / Prometheus**: export `status()` counters (`recent_count`, `max_total`, `warnings`, `critical_hits`) as gauges; or ship `UsageTracker` rows to a metrics pipeline.

### Where to hook
- Wrap each completed turn: call `token_monitor.record(in_tokens, out_tokens, context_tokens, session_id)` and `usage_tracker.record(model, in_tokens, out_tokens, session_id)`, then evaluate `should_fallback()` before assembling the next context.
- Log via `get_logger(__name__)` (`mcp_cli/services/logging.py`) — writes `~/.hiil/chat.log` (10 MB rotating, 5 backups).

---

## 5. Docker runbook

### Build
```bash
docker build -t hiil .
```

### Run (CLI)
```bash
# Interactive session, state persisted on the ./data bind mount:
docker run -it --rm -v ./data:/data \
  -e MODEL_API_KEY=... hiil

# Web gate override:
docker run -it --rm -p 8000:8000 -v ./data:/data \
  hiil uvicorn vajra_gate:app --host 0.0.0.0 --port 8000
```

### Compose
```bash
docker compose up -d --build        # start CLI service
docker compose exec hiil            # attach to the interactive CLI
docker compose run --rm hiil        # one-shot interactive session
docker compose --profile vector-db up -d   # additionally start Chroma
docker compose down
```

### Where data persists
- The image runs as non-root user `app` with `HOME=/data`; every `Path.home() / ".hiil"` path (vectors.db, users.db, chat.log, usage store, preferences) resolves under `/data`.
- Compose mounts the named volume `hiil_data:/data` (or use `./data:/data` for a host bind mount — create the dir first and make it writable by the container user).
- Volume contents survive `docker compose down` and image rebuilds; back up the volume or the bind-mount directory to preserve the vector store.

### Notes
- `.dockerignore` keeps `.venv`, caches, `node_modules`, `storage_files`, and local `data/` out of the image.
- The `ocr` extra (Pillow/pytesseract) is skipped for a lean image; re-enable with `pip install -e ".[ocr]"` inside the image if OCR is required.
- `docker build` was **not** verified in this environment (docker CLI unavailable) — validate the build on a machine with Docker before relying on it.
