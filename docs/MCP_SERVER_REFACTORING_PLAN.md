# MCP Server Rewrite Plan: `veda_engine` + `drishti_engine` → 6 Servers

> **Status: COMPLETED** — all 8 phases implemented and verified (2026-08-08).
> Full suite 793 passed / 20 failed (pre-existing `CliChat.tool_runner` only); ruff + mypy clean;
> all 6 servers SSE-boot on their ports; gateway ↔ shared-store contract verified. Archived as a
> record; no further action required.

## Scope

| Package | Action |
|---|---|
| `veda_engine` | REWRITE → 4 servers (workspace, doc, web, memory) |
| `drishti_engine` | REWRITE → 2 servers (media, drishti) |
| `vajra_gate` | UNTOUCHED — byte-identical, must keep working |
| `mcp_cli` | Wiring-only changes (config.yaml) |
| `setu_bridge` | UNTOUCHED |

**Constraint:** `vajra_gate/storage.py` imports `veda_engine.storage.store`, and
`veda_engine/tools/preferences.py` imports `vajra_gate.services.preferences`. The
rewrite keeps the gate→engine import working via a **compat shim** and breaks the
engine→gate import by re-homing preferences into `hiil_common`.

---

## Audit Facts (2026-08-08)

- **veda_engine**: one FastMCP `FastMCP("workspace-search")`, 17 tools + 2 resources
  (`docs://documents`, `docs://documents/{doc_id}`). Config: `HIIL_WORKSPACE` only, no dotenv.
  Storage: per-user SQLite `~/.hiil/docs_<user>.db` (WAL). Only engine→gate import:
  `tools/preferences.py:9` → `vajra_gate.services.preferences.UserPreferencesStore`.
- **drishti_engine**: one FastMCP `FastMCP("drishti")`, 8 tools, 0 resources.
  100% self-contained. Storage: `JsonStore` for browser history
  (`~/.hiil/store/browser_history.json`). Has its own SSRF guard in `tools/_net.py`.
- **Shared bugs to fix**: (1) `__main__.py` ignores `--transport/--port` (dead argparse
  under `python -m`); (2) no dotenv loading in engines; (3) `HIIL_WORKSPACE` vs
  `HIIL_WORKSPACE_DIR` mismatch; (4) drishti SSRF follows redirects without per-hop
  revalidation (veda re-validates each hop).

---

## Target Layout

```
hiil_common/                       # NEW shared package (no MCP surface)
├── __init__.py
├── config.py                      # load_dotenv(); workspace_root() [HIIL_WORKSPACE →
│                                  #   HIIL_WORKSPACE_DIR → cwd]; user_id() [HIIL_USER_ID]
├── utils/
│   ├── __init__.py
│   ├── paths.py                   # path-traversal guard (from veda tools/path_guard.py)
│   ├── shell_safety.py            # deny-by-verb shell guard (from veda tools/shell.py)
│   └── ssrf.py                    # validate_public_http_url + per-hop redirect revalidation
│                                  #   (unify veda tools/web.py + drishti tools/_net.py)
├── services/
│   ├── __init__.py
│   └── preferences.py             # standalone UserPreferencesStore → same
│                                  #   ~/.hiil/store/preferences.json (namespace "preferences"),
│                                  #   NO vajra_gate import
└── storage/
    ├── __init__.py
    └── json_store.py              # thread-safe JSON list store (moved from drishti_engine/storage/store.py)
                                   # NOTE: the SQLite doc store stays in veda_engine/storage/store.py
                                   #   (test_veda_store.py monkeypatches its module-level DB_DIR)

workspace_server/                  # NEW  FastMCP   port 8102
├── main.py                        # search_resources, glob, grep, read_text_resource,
│                                  #   read_text_batch, list_roots, read_dir, run_command
└── __main__.py                    # argparse --transport/--port
doc_server/                        # NEW  FastMCP   port 8101
├── main.py                        # read_document, edit_document, format_document
│                                  #   + resources docs://documents, docs://documents/{id}
└── __main__.py
web_server/                        # NEW  FastMCP   port 8103
├── main.py                        # web_search, web_fetch, summarize (MCP sampling)
└── __main__.py
memory_server/                     # NEW  FastMCP   port 8104
├── main.py                        # remember, recall, forget
└── __main__.py
media_server/                      # NEW  FastMCP   port 8401
├── main.py                        # graphic_art, search_template_images, search_template_videos
└── __main__.py
drishti_engine/                    # REWRITE in place  FastMCP  port 8400
├── main.py                        # search_flights, search_airports, search_healthcare,
│                                  #   browser_search, browser_add
├── __main__.py                    # fix argparse
├── data/                          # static catalogs (untouched)
└── storage/store.py               # re-export hiil_common.storage.json_store
```

**Compat shims (gateway stays byte-identical):**
- `veda_engine/storage/store.py` → REMAINS canonical. It is NOT moved to
  `hiil_common` because `tests/test_veda_store.py` monkeypatches its module-level
  `DB_DIR`; moving it would break that patch. `vajra_gate/storage.py` stays unchanged.
- `veda_engine/tools/path_guard.py` / `config.py` / `shell_safety.py` → thin shims
  re-exporting/delegating to `hiil_common` (module-level `WORKSPACE_ROOT` name kept so
  tests that monkeypatch `config_module.WORKSPACE_ROOT`/`shell_module.WORKSPACE_ROOT` work).
- `veda_engine/tools/preferences.py` → uses `hiil_common.services.preferences` (breaks the
  engine→gate import); `tests/test_preferences.py` `tool_store` fixture now patches
  `hiil_common.services.preferences.get_store`.
- `veda_engine/__init__.py` → lazy `mcp` via `__getattr__` forwarding to
  `workspace_server.main.mcp` so `veda_engine.py`, `examples/server.py`, and
  `mcp dev veda_engine.py` keep working (avoids the circular import:
  `workspace_server.main` imports `veda_engine.tools.*`).

---

## Implementation Steps

### Phase 1 — Extract `hiil_common` (no server changes; repo stays green)
- [x] `hiil_common/storage/json_store.py`: move `drishti_engine/storage/store.py` verbatim
      (Drishti re-exports it; `test_drishti_browser_history.py` patches `bh._history_store`,
      not the module, so this is safe).
- [x] `hiil_common/services/preferences.py`: standalone `UserPreferencesStore` (same JSON
      path/namespace, no `vajra_gate` import).
- [x] `hiil_common/utils/paths.py`, `utils/shell_safety.py`, `utils/ssrf.py`
      (unify + per-hop redirect revalidation).
- [x] `hiil_common/config.py`: `load_dotenv`, `workspace_root()`, `user_id()`.
- [x] `veda_engine/config.py` / `tools/path_guard.py` / `tools/shell_safety.py` → shims.
- [x] `veda_engine/tools/preferences.py` → `hiil_common.services.preferences`.
- [x] `drishti_engine/storage/store.py` → re-export shim; `tools/_net.py` → re-export shim;
      `config.py` → `WORKSPACE_ROOT` from `hiil_common.config`.
- [x] Verify: `tests/test_veda_store.py`, `tests/test_preferences.py`, `tests/test_web.py`,
      `tests/test_roots.py`, `tests/test_shell.py`, `tests/test_workspace_tools.py`,
      `tests/test_drishti_*.py` still green.

### Phase 2 — Build `workspace_server` (8102)
- [x] `main.py`: search_resources, glob, grep, read_text_resource, read_text_batch,
      list_roots, read_dir, run_command (exact names + arg schemas; via `hiil_common.config`,
      `utils.paths`, `utils.shell_safety`).
- [x] `__main__.py`: argparse honoring `--transport {stdio,sse,streamable-http}` / `--port`.

### Phase 3 — Build `doc_server` (8101)
- [x] `main.py`: read_document, edit_document, format_document + `docs://documents`,
      `docs://documents/{id}` resources (via `veda_engine.storage.store` — canonical SQLite
      store shared with the gateway).
- [x] `__main__.py`: argparse.

### Phase 4 — Build `web_server` (8103) + `memory_server` (8104)
- [x] `web_server/main.py`: web_search (DuckDuckGo), web_fetch (SSRF-guarded, per-hop
      redirect revalidation), summarize (MCP sampling). + `__main__.py`.
- [x] `memory_server/main.py`: remember/recall/forget via
      `hiil_common.services.preferences`. + `__main__.py`.

### Phase 5 — Rewrite `drishti_engine` → `media_server` (8401) + `drishti_engine` (8400)
- [x] `media_server/main.py`: graphic_art, search_template_images, search_template_videos
      (via `hiil_common.utils.ssrf`, config env `HIIL_PEXELS_API_KEY`/`HIIL_GRAPHIC_ART_URL`).
- [x] `drishti_engine/main.py`: search_flights, search_airports, search_healthcare,
      browser_search, browser_add (via `hiil_common.storage.json_store`, `data/` catalogs).
- [x] Fix `drishti_engine/__main__.py` argparse; `storage/store.py` → re-export shim.

### Phase 6 — Update `veda_engine` compat layer
- [x] `veda_engine/__init__.py` → lazy `mcp` (avoids circular import:
      `workspace_server.main` imports `veda_engine.tools.*`).
- [x] `veda_engine/main.py` → re-exports `workspace_server.main` (`mcp`/`main`).
- [x] Keep `veda_engine.py` + `examples/server.py` working.

### Phase 7 — Wire `mcp_cli`
- [x] `config.yaml`: replace `veda_engine` entry with `workspace_server`, `doc_server`,
      `web_server`, `memory_server`; add `media_server`; keep `drishti_engine`, refiner,
      filesystem, memory, everything, mock_mail, calendar.
- [x] `mcp_cli/services/agents/subagents.py`: `MEDIA_DESIGNER.capabilities` → `["media"]`
      (tool_router tags tools by server id; media tools now live in `media_server`).
- [x] `pyproject.toml`: add `hiil_common*`, `workspace_server`, `doc_server`, `web_server`,
      `memory_server`, `media_server` to setuptools `packages`.
- [x] Verify `server_manager.load_mcp_server` spawns `python -m <pkg> --transport sse --port <free>`
      and connects to `/sse` (needs `__main__` argparse — fixed in Phase 2-5).

### Phase 8 — Verify (gateway regression)
- [x] `pytest tests/` full — 793 passed / 20 failed (only pre-existing `CliChat.tool_runner`
      Gap-3 failures) + 1 skipped. All previously-green suites still green.
- [x] Contract test: `vajra_gate.storage` imports `veda_engine.storage.store` (canonical);
      `gs.create_document is store.create_document`; `doc_server` → `veda_engine.tools.documents`
      → same store functions.
- [x] Gateway in-process smoke via `tests.gate_helpers.make_client`: `POST /api/upload` →
      `GET /api/documents` → `GET /api/documents/{id}` all 200; doc_server `read_document`
      returns the same doc from the shared DB.
- [x] `ruff check` + `mypy` clean on `hiil_common`, all 5 new servers, `veda_engine/tools/shell.py`.
- [x] Smoke: SSE boot each server on its port (workspace 8102, doc 8101, web 8103, memory 8104,
      media 8401, drishti 8400) — all `SSE-OK`; SSRF guard rejects `http://127.0.0.1/`.

---

## Port Allocations (final)

| Port | Server | Tools |
|---|---|---|
| 8101 | `doc_server` | read_document, edit_document, format_document, docs:// resources |
| 8102 | `workspace_server` | search_resources, glob, grep, read_text_resource, read_text_batch, list_roots, read_dir, run_command |
| 8103 | `web_server` | web_search, web_fetch, summarize |
| 8104 | `memory_server` | remember, recall, forget |
| 8400 | `drishti_engine` | search_flights, search_airports, search_healthcare, browser_search, browser_add |
| 8401 | `media_server` | graphic_art, search_template_images, search_template_videos |
| 8000 | `vajra_gate` | (frozen, untouched) |
| 8300 | refiner | (frozen, untouched) |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Gateway breaks if shim diverges | Shim is a pure re-export; contract test locks it |
| Tool-name/schema drift breaks clients | Copy logic verbatim, preserve exact names + arg schemas |
| Preferences split-brain | Both write same JSON (atomic replace); single impl in hiil_common |
| Port conflicts with 8100/8200 scanners | Fixed per-server defaults; mcp_cli already scans upward |
| `data/` catalogs accidentally dropped | Move with their tools; golden-entry tests |

---

*Generated: 2026-08-08*
*Project: H.I.I.L. - Hyper-Integrated Inference Engine*
