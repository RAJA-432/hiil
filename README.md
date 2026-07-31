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
├── canvas_app/frontend/    # React SPA — chat, skills, file preview, charts
│   └── src/
│       ├── api/            # HTTP client, SSE streaming, mock layer (9 files)
│       ├── components/     
│       │   ├── Chat/       # ChatPanel, MessageBubble, markdown parser, KaryaCall, inline charts
│       │   ├── Composer/   # Text input with image paste/drag-drop, template picker
│       │   ├── Preview/    # Monaco editor, Markdown, Image, Diff renderers
│       │   ├── Sidebar/    # Conversation list, file tree, tags, inline rename, pinning
│       │   ├── Skills/     # Skills panel, prompt templates, connectors, active skill indicator
│       │   ├── Toolbar/    # Model picker, model info, settings, shortcuts, theme toggle
│       │   └── Shared/     # Modal, toast, search, export, undo snackbar, skeleton, welcome tour
│       ├── hooks/          # useChat, useSkills, useTags, useUndo, useToast, useWorkspace, useModels, useSettings (8 hooks)
│       ├── stores/         # localStorage persistence
│       └── styles/         # Single CSS file (~2,400 lines, custom properties, dark/light)
├── mcp_cli/                # Core engine — CliChat, RAG pipeline, agent runner
├── veda_engine/            # Built-in MCP tools — workspace, documents, web, roots
├── setu_bridge/            # MCP client wrapper
├── config.yaml             # Provider, model, server, root config
├── setup.ps1               # One-command setup
└── tests/                  # 86 tests (unit + shared fixtures)
```

## Testing

```bash
make test          # pytest -x -q (quick)
make test-v        # pytest -x -v (verbose)
make test-coverage # with coverage report
make lint          # ruff check
make lint-fix      # ruff check --fix
make format        # ruff format --check
make format-fix    # ruff format
make typecheck     # mypy static analysis
make check         # lint + typecheck + test (CI pipeline)

# Frontend
cd canvas_app/frontend
npx vitest run     # 21 tests
npx eslint src/    # lint
npx vite build     # production build
```

## Web UI Features

### Chat
- **SSE streaming** with real-time token rendering and blinking cursor
- **Multimodal input** — paste images from clipboard, drag-drop files, file picker; vision models receive the image directly, non-vision models get OCR-extracted text
- **Message actions** — copy, retry, edit (inline textarea + re-run), delete with undo
- **Conversation search** — full-text search within active conversation (Ctrl+F)
- **Inline charts** — detect pipe tables in messages → render SVG bar chart
- **Token usage bar** — real-time context window % with color thresholds
- **Export** — Download conversation as Markdown or JSON

### Skills (Persona System)
- **6 bundled personas** — Data Analyst, Code Reviewer, Writer, Architect, Researcher, General
- **Prompt templates** — 3-4 curated prompts per skill, one-click insert into composer
- **Tool presets** — each skill enables specific MCP tools
- **Filter and search** skills by category, search by name/description
- **Active indicator** — toolbar badge + system prompt bar in chat header

### Sidebar
- **Tabbed interface** — 💬 Chats / 🧠 Skills / 📁 Files
- **Conversation management** — create, delete, inline rename (double-click), pin to top
- **Tagging** — add/remove color-coded tags, filter by tag, all persisted to localStorage
- **Date grouping** — Today/Yesterday/This Week/Earlier with count badges
- **Recursive file tree** — expand/collapse directories, click to open in preview

### File Preview
- **Monaco Editor** — 23+ languages, read-only, minimap, line numbers, folding
- **Markdown renderer** — custom zero-dep parser with code blocks, tables, task lists, strikethrough, emoji shortcodes, auto-links
- **Image viewer** — blob URL fetch, auto-cleanup
- **Diff viewer** — collapsible file sections, add/del highlighting

### Customization
- **Settings modal** (Ctrl+,) — model, temperature, max tokens, API base URL, API key (show/hide), system prompt editor
- **Keyboard shortcuts** (Ctrl+K) — 10 shortcuts with cheat sheet
- **Dark/light theme** — persisted to localStorage, CSS custom properties
- **Resizable panels** — drag handles on sidebar and preview, widths persisted

### UI Utilities
- **Toast notifications** — success/error/info with auto-dismiss, color-coded
- **Undo snackbar** — undo message delete with 5-second window
- **Loading skeletons** — animated pulse placeholders during message load
- **Scroll-to-bottom** — floating button when scrolled up
- **Error boundary** — catches render errors with reload button
- **Welcome tour** — first-visit onboarding overlay
- **Connectors panel** — browse and toggle MCP servers, plugins, built-in tools

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Escape` | Stop generation / close modal |
| `Ctrl+K` | Toggle shortcuts modal |
| `Ctrl+,` | Toggle settings modal |
| `Ctrl+N` | New conversation |
| `Ctrl+\` | Toggle sidebar |
| `Ctrl+F` | Search within conversation |
| `Ctrl+L` | Focus sidebar search |

## Architecture Notes

- **Zero runtime deps** beyond React + Monaco Editor — markdown parser, charts, diff viewer, toast system all hand-rolled
- **Mock layer** in every API module (`VITE_USE_MOCK=true`) enables full UI development without a backend
- **Hook composition** — API layer → custom hook → components; swap API file to switch mock ↔ real backend
- **localStorage** for settings, tags, pinned conversations, tour completion — survives refresh

## Configuration

Edit `config.yaml` for provider, model, MCP servers, root dirs. Env vars in `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `VAJRA_GATE_CHAT_LOG` | `""` | Path to append SSE event JSON for every chat turn (one event per line). |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL. |
| `VAJRAM_CHAT_LOG` | — | Legacy alias for `VAJRA_GATE_CHAT_LOG`. |

## Built-in MCP Tools

`read_text_resource`, `read_dir`, `search_resources`, `glob`, `grep` — workspace fileops (path-traversal guarded). `read_document`, `edit_document` — stored document CRUD. `web_search`, `web_fetch` — DuckDuckGo + SSRF-protected fetch. `summarize` — delegates to LLM. `list_roots` — approved root dirs.
