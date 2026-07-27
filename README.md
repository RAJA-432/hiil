# hiil — MCP Chat + RAG + Agents

CLI + Web chat backed by MCP tool servers and Ollama. Built-in RAG — upload PDFs/DOCX/text, auto-retrieves context.

```
CLI/React → FastAPI → mcp_cli (chat, RAG, agents) → Ollama + MCP servers
```

## Quick Start

```powershell
.\setup.ps1              # build frontend + start server at :8000
.\setup.ps1 -Dev         # Vite hot-reload dev server at :5173
```

Open [http://localhost:8000](http://localhost:8000). CLI mode: `python main.py`

## Project Layout

```
hiil/
├── vajra_gate/             # FastAPI gateway — auth, SSE streaming, file endpoints
│   └── routers/            # auth, chat, sessions, knowledge, agents, files
├── canvas_app/frontend/    # React SPA — chat, file preview, Monaco editor
├── mcp_cli/                # Core engine — CliChat, RAG pipeline, agent runner
├── veda_engine/            # Built-in MCP tools — workspace, documents, web, roots
├── setu_bridge/            # MCP client wrapper
├── config.yaml             # Provider, model, server, root config
├── setup.ps1               # One-command setup
└── tests/                  # ~900 tests
```

## Configuration

Edit `config.yaml` for provider, model, MCP servers, root dirs. Env vars in `.env`.

## Built-in MCP Tools

`read_text_resource`, `read_dir`, `search_resources`, `glob`, `grep` — workspace fileops (path-traversal guarded). `read_document`, `edit_document` — stored document CRUD. `web_search`, `web_fetch` — DuckDuckGo + SSRF-protected fetch. `summarize` — delegates to LLM. `list_roots` — approved root dirs.