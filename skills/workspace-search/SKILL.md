# Workspace Search

Search and read files in the project workspace rooted at `cwd()`.

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `search_resources` | `(query: str) -> list[str]` | Find files whose name contains `query` (case-insensitive). Returns up to 50 relative paths. |
| `glob` | `(pattern: str) -> list[str]` | Find files matching a glob pattern (e.g. `**/*.py`). |
| `grep` | `(pattern: str, include: str = "") -> list[dict]` | Search file contents by regex, optionally filtered by file pattern. Returns `{file, line, line_number}`. |
| `read_text_resource` | `(path: str) -> str` | Read a text file by its relative workspace path. Path traversal is blocked. |
| `read_dir` | `(path: str = ".") -> str` | List directory contents with type indicators. Respects root boundaries. |
| `list_roots` | `() -> list[dict]` | List approved root directories and their names. |
| `summarize` | `(text_to_summarize: str) -> str` | Summarize text via the client's LLM (sampling protocol). |

## Usage

- `search_resources("config")` → `["config.yaml", "src/config.py"]`
- `glob("*.yaml")` → `["config.yaml"]`
- `grep("class .+Manager", "*.py")` → `[{file: "src/manager.py", line: "class RootsManager:", line_number: 12}]`
- `read_text_resource("config.yaml")` → raw file contents
- `read_dir("src")` → directory listing
- `list_roots()` → approved root directories
- `summarize("long text...")` → concise summary
- Always use `read_text_resource` first after `search_resources` to inspect contents.
