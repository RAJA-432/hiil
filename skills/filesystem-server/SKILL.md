# Filesystem Server

Full read/write filesystem access via `@modelcontextprotocol/server-filesystem`, rooted at the project directory (`.`).

## Tools

| Tool | Signature | Description |
|------|-----------|-------------|
| `read_file` | `(path: str) -> str` | Read a file's contents as text |
| `read_multiple_files` | `(paths: list[str]) -> str` | Read multiple files at once |
| `write_file` | `(path: str, content: str) -> str` | Write (overwrite) a file |
| `edit_file` | `(path: str, old: str, new: str) -> str` | Find/replace in a file |
| `create_directory` | `(path: str) -> str` | Create a new directory |
| `list_directory` | `(path: str) -> list` | List directory contents with metadata |
| `directory_tree` | `(path: str) -> str` | Recursive directory tree view |
| `move_file` | `(source: str, dest: str) -> str` | Move/rename a file |
| `copy_file` | `(source: str, dest: str) -> str` | Copy a file |
| `get_file_info` | `(path: str) -> dict` | File metadata (size, dates, type) |
| `search_files` | `(pattern: str, root: str) -> list[str]` | Search files by glob pattern |
| `get_allowed_directories` | `() -> list[str]` | List allowed root directories |

## Notes

- All paths are relative to the allowed root (`hiil/` project directory).
- Path traversal outside the root is denied.
