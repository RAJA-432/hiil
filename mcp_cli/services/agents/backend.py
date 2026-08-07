from __future__ import annotations

import fnmatch
import json
import shutil
from pathlib import Path
from typing import Any


class VirtualBackend:
    """Virtual filesystem that intercepts MCP file tool calls.

    By default, all file operations go to an in-memory dict — agents
    never touch the real disk.  Route overrides map virtual path prefixes
    to real filesystem directories so selected outputs persist.

    Usage::

        backend = VirtualBackend()
        backend.add_route("/output/", "/home/user/project/output/")

        # write_file, read_file, list_directory all route through here.
        # Writes to /output/* land on real disk; writes to /tmp/* stay in memory.
    """

    _FILE_TOOLS: set[str] = {
        "read_file",
        "read_multiple_files",
        "write_file",
        "edit_file",
        "list_directory",
        "move_file",
        "copy_file",
        "get_file_info",
        "create_directory",
        "delete_file",
        "delete_directory",
        "search_files",
    }

    def __init__(self) -> None:
        self._files: dict[str, str] = {}
        self._dirs: dict[str, list[dict[str, Any]]] = {}
        self._routes: list[tuple[str, Path]] = []

    # ------------------------------------------------------------------
    # Route management
    # ------------------------------------------------------------------

    def add_route(self, virtual_prefix: str, real_path: str | Path) -> None:
        resolved = Path(real_path).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        norm_prefix = virtual_prefix.rstrip("/") + "/"
        self._routes.append((norm_prefix, resolved))

    def _resolve_route(self, virtual_path: str) -> tuple[str | None, Path | None]:
        norm_path = virtual_path.rstrip("/") + "/"
        for prefix, real_dir in self._routes:
            if norm_path.startswith(prefix):
                rel = norm_path[len(prefix):].rstrip("/")
                return (prefix, real_dir / rel if rel else real_dir)
        return (None, None)

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def can_handle(self, tool_name: str) -> bool:
        return tool_name in self._FILE_TOOLS

    def handle_tool(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Handle a tool call.  Returns result text or ``None`` to pass through."""
        handler = getattr(self, f"_handle_{tool_name}", None)
        if handler is None:
            return None
        try:
            return handler(args)
        except Exception as exc:
            return f"[virtual-backend error] {exc}"

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _handle_read_file(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        prefix, real = self._resolve_route(path)
        if real and real.exists():
            return real.read_text(encoding="utf-8")
        content = self._files.get(path)
        if content is not None:
            return content
        return f"[virtual-backend] File not found: {path}"

    def _handle_read_multiple_files(self, args: dict[str, Any]) -> str:
        paths = args.get("paths", [])
        parts: list[str] = []
        for p in paths:
            content = self._handle_read_file({"path": p})
            parts.append(f"--- {p} ---\n{content}")
        return "\n\n".join(parts)

    def _handle_write_file(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        content = args.get("content", "")
        prefix, real = self._resolve_route(path)
        if real:
            real.parent.mkdir(parents=True, exist_ok=True)
            real.write_text(content, encoding="utf-8")
            return f"Written to {real} ({len(content)} bytes)"
        self._files[path] = content
        return f"Written to virtual path {path} ({len(content)} bytes)"

    def _handle_edit_file(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        old = args.get("oldString", "")
        new = args.get("newString", "")
        prefix, real = self._resolve_route(path)
        if real and real.exists():
            text = real.read_text(encoding="utf-8")
            if old not in text:
                return f"[virtual-backend] oldString not found in {path}"
            real.write_text(text.replace(old, new), encoding="utf-8")
            return f"Edited {real}"
        text = self._files.get(path, "")
        if old not in text:
            return f"[virtual-backend] oldString not found in {path}"
        self._files[path] = text.replace(old, new)
        return f"Edited virtual path {path}"

    def _handle_list_directory(self, args: dict[str, Any]) -> str:
        path = args.get("path", ".")
        norm_path = path.rstrip("/") + "/"
        prefix, real = self._resolve_route(path)
        entries: list[dict[str, Any]] = []
        if real and real.exists():
            for child in sorted(real.iterdir()):
                entries.append({
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else 0,
                })
        for vpath in self._files:
            if vpath.startswith(norm_path) or vpath == path:
                name = vpath.rsplit("/", 1)[-1]
                if not any(e["name"] == name for e in entries):
                    entries.append({
                        "name": name,
                        "type": "file",
                        "size": len(self._files[vpath]),
                    })
        return json.dumps(entries, indent=2)

    def _handle_get_file_info(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        prefix, real = self._resolve_route(path)
        if real and real.exists():
            st = real.stat()
            return json.dumps({
                "path": path,
                "size": st.st_size,
                "type": "directory" if real.is_dir() else "file",
            })
        content = self._files.get(path)
        if content is not None:
            return json.dumps({
                "path": path,
                "size": len(content),
                "type": "file",
            })
        return f"[virtual-backend] Not found: {path}"

    def _handle_create_directory(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        prefix, real = self._resolve_route(path)
        if real:
            real.mkdir(parents=True, exist_ok=True)
            return f"Directory created: {real}"
        return f"[virtual-backend] Directory creation not supported for virtual path {path} (add a route)"

    def _handle_delete_file(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        prefix, real = self._resolve_route(path)
        if real and real.exists():
            if real.is_dir():
                return f"[virtual-backend] {path} is a directory; use delete_directory"
            real.unlink()
            return f"Deleted {real}"
        if path in self._files:
            del self._files[path]
            return f"Deleted virtual path {path}"
        return f"[virtual-backend] File not found: {path}"

    def _handle_delete_directory(self, args: dict[str, Any]) -> str:
        path = args.get("path", "")
        prefix, real = self._resolve_route(path)
        if real and real.exists():
            if not real.is_dir():
                return f"[virtual-backend] {path} is a file; use delete_file"
            shutil.rmtree(real)
            return f"Deleted directory {real}"
        norm_path = path.rstrip("/") + "/"
        removed = [p for p in self._files if p.startswith(norm_path) or p == path]
        if not removed and path not in self._files:
            return f"[virtual-backend] Directory not found: {path}"
        for p in removed:
            del self._files[p]
        return f"Deleted virtual directory {path} ({len(removed)} files)"

    def _handle_move_file(self, args: dict[str, Any]) -> str:
        source = args.get("source", "")
        dest = args.get("dest", "")
        content = self._files.pop(source, None)
        if content is not None:
            self._files[dest] = content
            return f"Moved virtual {source} -> {dest}"
        prefix_s, real_s = self._resolve_route(source)
        prefix_d, real_d = self._resolve_route(dest)
        if real_s and real_d and real_s.exists():
            real_s.rename(real_d)
            return f"Moved {real_s} -> {real_d}"
        return f"[virtual-backend] Cannot move {source}"

    def _handle_copy_file(self, args: dict[str, Any]) -> str:
        source = args.get("source", "")
        dest = args.get("dest", "")
        content = self._files.get(source)
        if content is not None:
            self._files[dest] = content
            return f"Copied virtual {source} -> {dest}"
        prefix_s, real_s = self._resolve_route(source)
        if real_s and real_s.exists():
            content = real_s.read_text(encoding="utf-8")
            prefix_d, real_d = self._resolve_route(dest)
            if real_d:
                real_d.parent.mkdir(parents=True, exist_ok=True)
                real_d.write_text(content, encoding="utf-8")
                return f"Copied {real_s} -> {real_d}"
            self._files[dest] = content
            return f"Copied {real_s} -> virtual {dest}"
        return f"[virtual-backend] Cannot copy {source}"

    def _handle_search_files(self, args: dict[str, Any]) -> str:
        pattern = args.get("pattern", "")
        root = args.get("root", "")
        norm_root = root.rstrip("/") + "/" if root else ""
        matches: list[str] = []
        for vpath in self._files:
            if norm_root and not vpath.startswith(norm_root):
                continue
            if fnmatch.fnmatch(vpath, pattern) or pattern in vpath:
                matches.append(vpath)
        prefix, real = self._resolve_route(root or ".")
        if real and real.exists():
            for p in real.rglob("*"):
                rel = str(p.relative_to(real))
                if pattern in rel:
                    matches.append(rel)
        return json.dumps(matches)

    # ------------------------------------------------------------------
    # State extraction
    # ------------------------------------------------------------------

    @property
    def files(self) -> dict[str, str]:
        return dict(self._files)

    def get_file(self, path: str) -> str | None:
        return self._files.get(path)

    def list_virtual_paths(self) -> list[str]:
        return sorted(self._files.keys())
