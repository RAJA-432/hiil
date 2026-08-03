import logging
import mimetypes
import os
from datetime import UTC, datetime

logger = logging.getLogger("vajra_gate")

IGNORED_NAMES = frozenset({
    ".venv", "venv", ".env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".git", ".vscode", ".idea",
    "node_modules",
    "htmlcov", ".tox", ".eggs",
    "dist", "build",
})


class FileSystem:
    def __init__(self, root: str, ignore: frozenset[str] | None = None):
        self._root = os.path.realpath(root)
        self._ignore = ignore or IGNORED_NAMES

    def resolve(self, path: str) -> str:
        resolved = os.path.realpath(os.path.join(self._root, path))
        if not resolved.startswith(self._root):
            raise PermissionError(f"Path traversal denied: {path}")
        return resolved

    def relpath(self, safe_path: str) -> str:
        return os.path.relpath(safe_path, self._root).replace(os.sep, "/")

    def _should_ignore(self, name: str) -> bool:
        return name in self._ignore or name.endswith(".egg-info")

    def build_tree(self, path: str = ".", max_depth: int = 10) -> dict | None:
        safe = self.resolve(path)
        return self._build_tree(safe, max_depth)

    def _build_tree(self, safe_path: str, max_depth: int, depth: int = 0, visited: set[str] | None = None) -> dict | None:
        if visited is None:
            visited = set()
        name = os.path.basename(safe_path) or safe_path
        if self._should_ignore(name):
            return None
        if not os.path.isdir(safe_path):
            stat = os.stat(safe_path)
            return {"name": name, "type": "file", "path": self.relpath(safe_path), "size": stat.st_size}
        if depth >= max_depth:
            return {"name": name, "type": "dir", "path": self.relpath(safe_path), "children": []}
        real = os.path.realpath(safe_path)
        if real in visited:
            return {"name": name, "type": "dir", "path": self.relpath(safe_path), "children": []}
        visited.add(real)
        try:
            entries = sorted(os.listdir(safe_path), key=lambda x: (not os.path.isdir(os.path.join(safe_path, x)), x.lower()))
        except PermissionError:
            return {"name": name, "type": "dir", "path": self.relpath(safe_path), "children": []}
        children = []
        for entry in entries:
            full = os.path.join(safe_path, entry)
            child = self._build_tree(full, max_depth, depth + 1, visited)
            if child is not None:
                children.append(child)
        return {"name": name, "type": "dir", "path": self.relpath(safe_path), "children": children}

    def list_dir(self, path: str = ".") -> list[dict]:
        safe = self.resolve(path)
        if not os.path.isdir(safe):
            return []
        entries = sorted(os.listdir(safe), key=lambda x: (not os.path.isdir(os.path.join(safe, x)), x.lower()))
        items = []
        for name in entries:
            if self._should_ignore(name):
                continue
            full = os.path.join(safe, name)
            stat = os.stat(full)
            is_dir = os.path.isdir(full)
            items.append({
                "name": name,
                "type": "dir" if is_dir else "file",
                "path": self.relpath(full),
                "size": 0 if is_dir else stat.st_size,
            })
        return items

    def read_file(self, path: str) -> tuple[str | bytes, str | None, dict]:
        safe = self.resolve(path)
        if not os.path.isfile(safe):
            raise FileNotFoundError(f"File not found: {path}")
        mime_type, _ = mimetypes.guess_type(safe)
        stat = os.stat(safe)
        headers = {
            "X-File-Path": path,
            "X-File-Size": str(stat.st_size),
            "X-File-MTime": str(datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()),
        }
        if mime_type and not mime_type.startswith("text/"):
            with open(safe, "rb") as f:
                return f.read(), mime_type, headers
        with open(safe, encoding="utf-8", errors="replace") as f:
            return f.read(), "text/plain", headers

    def write_file(self, path: str, content: str) -> str:
        safe = self.resolve(path)
        parent = os.path.dirname(safe)
        os.makedirs(parent, exist_ok=True)
        with open(safe, "w", encoding="utf-8") as f:
            f.write(content)
        return self.relpath(safe)

    def create_dir(self, path: str) -> str:
        safe = self.resolve(path)
        os.makedirs(safe, exist_ok=True)
        return self.relpath(safe)

    def delete(self, path: str) -> str:
        safe = self.resolve(path)
        if not os.path.exists(safe):
            raise FileNotFoundError(f"Not found: {path}")
        if os.path.isdir(safe):
            os.rmdir(safe)
        else:
            os.remove(safe)
        return self.relpath(safe)

    def rename(self, path: str, new_path: str) -> tuple[str, str]:
        safe = self.resolve(path)
        safe_new = self.resolve(new_path)
        parent = os.path.dirname(safe_new)
        os.makedirs(parent, exist_ok=True)
        os.rename(safe, safe_new)
        return self.relpath(safe_new), self.relpath(safe)

    def exists(self, path: str) -> bool:
        try:
            return os.path.exists(self.resolve(path))
        except PermissionError:
            return False

    def is_dir(self, path: str) -> bool:
        try:
            return os.path.isdir(self.resolve(path))
        except PermissionError:
            return False
