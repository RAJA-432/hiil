# hiil — MCP Chat with Web UI
 
CLI + Web chat backed by MCP tool servers. Uses Ollama by default.
 
## 🚀 Why hiil?
**Stop prompting, start orchestrating.** 
Standard LLM interfaces are black boxes. `hiil` gives you a glass box:
- **Direct Filesystem Access**: Your LLM can `grep` your actual code and `glob` your workspace.
- **Agentic Control**: Spawn isolated agents with virtual filesystems and custom memory.
- **HITL (Human-in-the-Loop)**: No more "hallucinated" writes. Set tools to `interrupt_on`, review the agent's plan, edit the arguments, and then hit resume.
- **MCP Native**: Fully compatible with the Model Context Protocol for plug-and-play tool integration.

## Overview
hiil is an AI orchestrator that combines a high-performance CLI and a FastAPI-based web gateway (**Vajram**) to interact with LLMs through the Model Context Protocol (MCP). 

Unlike standard chat interfaces, hiil provides:
- **Local Workspace Integration**: Native tools for `grep`, `glob`, and file manipulation within approved root directories.
- **Autonomous Agents**: Spawn isolated AI subprocesses with their own memory, permissions, and virtual filesystems.
- **Human-in-the-Loop (HITL)**: Precise control over agent execution with the ability to pause, edit tool arguments, and resume tasks.
- **Multi-Transport MCP**: Support for `stdio`, `sse`, and `streamable-http` transports for flexible server deployment.
 
## Quick Start

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a model pulled, e.g.:
  ```bash
  ollama pull gemma4:31b-cloud
  ```
- Node.js 18+ (for npm-based MCP servers like `@modelcontextprotocol/server-filesystem`)

### 2. Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -e .
```

### 3. Launch Web UI

```bash
python -m vajram
```

Open **http://127.0.0.1:8000/chat** in your browser.

The gateway auto-launches Streamlit on port 8501 as a subprocess. All API endpoints are open (no auth).

## Configuration

Edit `config.yaml` to change provider, model, MCP servers, and root directories:

```yaml
settings:
  provider: "ollama"                     # ollama | openrouter | opencode
  model: "gemma4:31b-cloud"
  base_url: "http://localhost:11434/v1"  # Ollama default
  max_context_tokens: 200000

roots:
  - "."          # Filesystem tools can only access paths within these roots

servers:
  - id: "filesystem"
    script: "@modelcontextprotocol/server-filesystem"
    args: ["."]
```

Set environment variables in `.env` (create if missing):

```env
MODEL_PROVIDER=ollama
MODEL_NAME=gemma4:31b-cloud
MODEL_API_KEY=                 # only needed for OpenRouter/OpenCode
```

## Transport Modes

MCP servers support three transport modes:

| Transport | Description |
|-----------|-------------|
| `stdio` (default) | Server runs as a subprocess with stdio pipes |
| `sse` | Each server listens on its own HTTP port; client connects via Server-Sent Events |
| `streamable-http` | Newer HTTP transport using JSON-RPC POST + GET SSE for server-initiated events |

Set the mode globally via environment variable:

```bash
# PowerShell
$env:MCP_TRANSPORT = "streamable-http"; python -m vajram

# cmd
set MCP_TRANSPORT=streamable-http && python -m vajram
```

Or per-server in `config.yaml`:

```yaml
servers:
  - id: "filesystem"
    script: "@modelcontextprotocol/server-filesystem"
    transport: sse
```

Port ranges:
- SSE: starts at 8100 (`MCP_SSE_BASE_PORT`)
- Streamable HTTP: starts at 8200 (`MCP_HTTP_BASE_PORT`)

### Run a server standalone

```bash
python -m mcp_server.main --transport stdio           # stdio (default)
python -m mcp_server.main --transport sse --port 8100
python -m mcp_server.main --transport streamable-http --port 8200
```

## MCP Roots (Filesystem Access Control)

Roots define which directories MCP servers may access. They act as a permission boundary — any tool call that touches the filesystem is validated against the approved roots.

**Configuration** in `config.yaml`:

```yaml
roots:
  - "."                # project root
  - "/shared/data"     # additional directories
```

**Three layers of enforcement:**

1. **Client-side (ToolRunner)**: Every `read_file`, `write_file`, `list_directory`, etc. is checked against roots before calling the server
2. **MCP Protocol**: Roots are exposed to servers via the `list_roots` callback — servers can use `ctx.session.list_roots()` to discover approved paths
3. **Server-side (is_path_allowed)**: The built-in `read_dir` tool checks paths against client-provided roots

**CLI commands:**
- `/roots` — list approved root directories
- `/ls [path]` — list directory contents (respects root boundaries)

## MCP Sampling (LLM Delegation)

The MCP sampling protocol lets a server request LLM inference from the client without holding its own API key.

**Built-in tool:**
- `summarize(text_to_summarize)` — delegates text summarization to the client's LLM via `ctx.session.create_message()`

The sampling callback is wired automatically in `factory.py` — it converts `SamplingMessage` objects to OpenAI-format messages and calls the configured LLM provider.

## CLI Mode

```bash
python main.py
```

### Commands

| Command | Description |
|---------|-------------|
| `/new` | Start a new session |
| `/session <id>` | Switch to a session |
| `/sessions` | List saved sessions |
| `/model <name>` | Show or switch the model |
| `/models` | List available models |
| `/provider <name>` | Show or switch the provider |
| `/tools` | List available MCP tools |
| `/servers` | List active MCP servers |
| `/status` | Show system status |
| `/usage` | Show token usage and cost |
| `/roots` | List approved root directories |
| `/ls [path]` | List directory contents |
| `/web_search <q>` | Search the web (DuckDuckGo) |
| `/web_fetch <url>` | Fetch text content from a URL |
| `/load <script>` | Dynamically load a new MCP server |
| `/unload <id>` | Unload an MCP server |
| `/reload <id>` | Restart an MCP server |
| `/history [id]` | Show recent messages |
| `/export` | Export transcript to file |
| `/copy` | Copy last assistant message |
| `/search <q>` | Search session messages |
| `/semsearch <q>` | Semantic vector search |
| `/undo [n]` | Undo last n exchanges |
| `/fork <id>` | Fork messages from another session |
| `/rename <n>` | Rename current session |
| `/compact` | Compact session history |
| `/timer start\|stop` | Track session time |
| `/theme [name]` | Show or switch color theme |
| `/timestamp` | Toggle timestamps in history |
| `/key set\|delete\|status` | Manage encrypted API keys |
| `/agent create\|list\|...` | Manage background agents |
| `/plan` | Interactive model picker |
| `/help` | Show this help |
| `/exit` / `/quit` | Leave the chat |

## Agents

hiil agents are isolated, single-purpose AI subprocesses spawned from within a chat session. Each agent has its own system prompt, tool access, memory, permissions, and middleware.

### Configuration

Create an agent via `POST /api/agents` with the following config:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | — | Human-readable name |
| `role` | string | — | Role description (becomes system prompt) |
| `capabilities` | string[] | `[]` | Tool capability tags (`"filesystem"`, `"github"`, etc.) |
| `system_prompt` | string | `""` | Override default system prompt |
| `model` | string | `"default"` | Model override |
| `max_iterations` | int | 10 | Max LLM-tool cycles (1–100) |
| `timeout_seconds` | int | 300 | Max wall-clock time (1–3600) |
| `token_budget` | int | 0 | 0 = inherit parent limit |
| `interrupt_on` | dict | `{}` | Tools requiring human approval before execution |
| `memory_files` | string[] | `[]` | File paths for persistent agent memory |
| `permissions` | object[] | `[]` | Per-operation path-glob allow/deny rules |
| `middleware` | object[] | `[]` | Middleware pipeline entries (dict specs or instances) |

### Human-in-the-Loop

Gate specific tools for manual approval. The agent pauses and emits an SSE
interrupt event; a human can approve, edit the arguments, reject, or respond.

```json
{
  "interrupt_on": {
    "send_email": true,
    "add_customer": {"allowed_decisions": ["approve", "edit", "reject", "respond"]}
  }
}
```

Resume via `POST /api/agents/{id}/resume` with decisions:

```json
{
  "decisions": [
    {"type": "approve"},
    {"type": "edit", "edited_action": {"name": "add_customer", "args": {"name": "Alice"}}},
    {"type": "reject", "message": "Not now"},
    {"type": "respond", "message": "Use a different template"}
  ]
}
```

### Filesystem Permissions

Restrict which file operations an agent can perform and on which paths.
Rules are evaluated in order; the first match wins.

```json
{
  "permissions": [
    {"operations": ["read"], "paths": ["/data/**"], "mode": "allow"},
    {"operations": ["write"], "paths": ["/**"], "mode": "deny"}
  ]
}
```

Supported operations: `read`, `write`, `edit`, `list`, `search`, `copy`, `move`.

### Per-Agent Memory

Agents can read/write persistent files stored in `.agent_memory/<agent_id>/`.
List paths in `memory_files` — they are injected into the system prompt before
execution and persisted when the agent completes.

```json
{
  "memory_files": ["/AGENTS.md", "/notes.md"]
}
```

### Virtual Filesystem

Every agent gets an in-memory filesystem that intercepts MCP file tools
(`read_file`, `write_file`, `edit_file`, `copy_file`, `move_file`,
`list_directory`, `search_files`, `read_multiple_files`, `get_file_info`).
By default nothing touches real disk.

Use `POST /api/agents/{id}/route` to persist selected prefixes to real paths:

```json
{
  "virtual_prefix": "/output/",
  "real_path": "./agent_output/"
}
```

### Middleware Pipeline

Middleware hooks into the agent lifecycle to inject extra tools, transform
messages, or intercept tool calls. Pass middleware as dict specs over REST:

```json
{
  "middleware": [
    {"type": "code_interpreter", "timeout": 30},
    {"type": "summarization", "max_messages": 20}
  ]
}
```

Available middleware:

| Type | Constructor params | Description |
|------|--------------------|-------------|
| `code_interpreter` | `timeout` (int, default 15) | Subprocess-isolated Python execution with restricted builtins |
| `summarization` | `max_messages` (int, default 30), `summary_prompt` (string) | Auto-compresses conversation at message count threshold |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message (streaming or blocking) |
| POST | `/api/upload` | Upload a file to the document store |
| GET | `/api/documents` | List stored documents |
| GET | `/api/documents/{id}` | Get document content |
| GET | `/api/status` | Server status |
| GET | `/api/models` | List models |
| POST | `/api/model` | Switch active model |
| GET | `/api/sessions` | List sessions |
| POST | `/api/session/new` | Create new session |
| POST | `/api/session/switch` | Switch active session |
| GET | `/api/history/{id}` | Load session history |
| GET | `/api/tools` | List available tools |
| POST | `/api/tools/call` | Invoke a tool by name |
| POST | `/api/agents` | Create an agent |
| GET | `/api/agents` | List agents |
| GET | `/api/agents/{id}` | Get agent state + `virtual_files` |
| POST | `/api/agents/{id}/run` | Execute an agent (SSE stream supported) |
| POST | `/api/agents/{id}/resume` | Resume a paused agent with HITL decisions |
| POST | `/api/agents/{id}/route` | Add a virtual-to-real path route |
| POST | `/api/agents/{id}/stop` | Stop a running agent |
| GET | `/health` | Health check |
| GET | `/chat` | Web chat UI |
| WS | `/_stcore/stream` | Streamlit WebSocket proxy |

## MCP Server Tools

The built-in MCP server (`mcp_server`) exposes:

| Tool | Description |
|------|-------------|
| `search_resources` | Find files by name |
| `glob` | Find files by glob pattern |
| `grep` | Search file contents by regex |
| `read_text_resource` | Read a text file from workspace |
| `read_document` | Read a document by ID |
| `edit_document` | Edit a document (find/replace) |
| `format_document` | Format document content |
| `list_roots` | List approved root directories |
| `read_dir` | List directory contents (root-enforced) |
| `summarize` | Summarize text via client LLM sampling |
| `web_search` | Search the web (DuckDuckGo, no API key) |
| `web_fetch` | Fetch and extract text from a URL |

## Project Structure

```
hiil/
├── main.py                 # CLI entry point
├── vajram/                 # FastAPI web gateway
├── mcp_cli/                # CLI core library
│   ├── services/
│   │   ├── agents/         # Agent spawning + bridge features
│   │   │   ├── models.py           # AgentConfig, AgentState, AgentResult
│   │   │   ├── runner.py           # AgentRunner: execute loop, HITL, memory inject
│   │   │   ├── interrupts.py       # HITL vocabulary (ActionRequest, ResumeDecision, AgentInterrupt)
│   │   │   ├── permissions.py      # FilesystemPermission, PermissionEnforcer
│   │   │   ├── memory.py           # AgentMemoryStore (per-agent file namespace)
│   │   │   ├── backend.py          # VirtualBackend (in-memory filesystem with route-to-disk)
│   │   │   ├── middleware.py       # AgentMiddleware ABC + MiddlewarePipeline
│   │   │   ├── code_interpreter.py # Subprocess-isolated Python eval middleware
│   │   │   └── summarization.py    # Auto-compress conversation middleware
│   │   ├── roots.py        # RootsManager for filesystem access control
│   │   ├── chat.py         # CliChat session manager
│   │   ├── factory.py      # Chat creation with roots + sampling wiring
│   │   ├── tool_router.py  # Capability-based tool filtering
│   │   ├── tool_runner.py  # Tool execution with root enforcement
│   │   └── ...
│   ├── commands/           # CLI command implementations
│   └── ui/                 # prompt_toolkit-based CLI UI
├── mcp_client/             # MCP client wrapper (stdio, sse, streamable-http)
│   ├── connection.py       # ManagedConnection with roots + sampling callbacks
│   └── main.py             # MCPClient high-level API
├── mcp_server/             # MCP server with workspace + document tools
│   ├── tools/
│   │   ├── workspace.py    # search_resources, glob, grep, read_text_resource
│   │   ├── documents.py    # read_document, edit_document, format_document
│   │   ├── roots.py        # list_roots, read_dir, is_path_allowed
│   │   └── summarize.py    # summarize (uses client sampling)
│   └── main.py             # Server entry (stdio/sse/streamable-http)
├── config.yaml             # Provider, servers, roots config
├── .env                    # Environment variables
└── tests/
    ├── unit/               # Isolated unit tests
    ├── integration/        # I/O and subprocess tests
    └── e2e/                # Full API & CLI end-to-end tests
```
