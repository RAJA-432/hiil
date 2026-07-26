from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_cli.services.logging import get_logger

logger = get_logger("roots")


class RootsManager:
    """Manages approved root directories that MCP servers may access.

    Roots act as a permission boundary: any tool call that accesses the
    filesystem must first pass through ``is_path_allowed()`` to verify
    the target path falls within an approved root directory.

    Roots are configured in ``config.yaml`` under the ``roots:`` section
    and can also be injected at runtime via ``add_root()``.
    """

    def __init__(self, roots: list[str] | None = None):
        self._roots: list[Path] = []
        for r in roots or []:
            self.add_root(r)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_root(self, path: str | Path) -> None:
        """Add an approved root directory.

        Resolves to an absolute path and caches it.  Duplicates are
        silently ignored.
        """
        resolved = Path(path).expanduser().resolve()
        if resolved in self._roots:
            return
        if not resolved.is_dir():
            logger.warning("Root path '%s' is not a directory — adding anyway", resolved)
        self._roots.append(resolved)
        logger.debug("Added root: %s", resolved)

    @property
    def roots(self) -> list[Path]:
        return list(self._roots)

    def list_roots(self) -> list[dict[str, Any]]:
        return [
            {
                "path": str(r),
                "name": r.name,
            }
            for r in self._roots
        ]

    def is_path_allowed(self, target_path: str | Path) -> bool:
        """Check whether *target_path* falls within any approved root.

        Returns ``True`` if the resolved absolute path is inside (or equal
        to) at least one root directory.  Path-traversal attacks that
        escape via ``..`` are also caught because the path is resolved
        before the comparison.
        """
        target = Path(target_path).expanduser().resolve()
        for root in self._roots:
            try:
                target.relative_to(root)
                return True
            except ValueError:
                continue
        logger.debug("Path '%s' is not within any approved root", target)
        return False

    def enforce_path(self, target_path: str | Path, tool_name: str = "") -> str | None:
        """Return an error message if *target_path* is not allowed, else ``None``."""
        if self.is_path_allowed(target_path):
            return None
        roots_list = ", ".join(str(r) for r in self._roots) or "(none configured)"
        return (
            f"[denied] Path '{target_path}' is not within approved roots ({roots_list})"
            + (f" for tool '{tool_name}'" if tool_name else "")
        )

    # ------------------------------------------------------------------
    # Argument inspection helpers
    # ------------------------------------------------------------------

    def inspect_tool_args(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Inspect *args* for likely path values and enforce roots.

        Returns an error string if any argument that looks like a file
        path refers to a disallowed location, else ``None``.
        """
        path_candidates = self._extract_paths(tool_name, args)
        for label, val in path_candidates:
            err = self.enforce_path(val, tool_name)
            if err:
                return err
        return None

    @staticmethod
    def _extract_paths(tool_name: str, args: dict[str, Any]) -> list[tuple[str, str]]:
        tools_with_root_arg = {
            "read_file",
            "read_multiple_files",
            "write_file",
            "edit_file",
            "list_directory",
            "directory_tree",
            "move_file",
            "copy_file",
            "get_file_info",
            "search_files",
            "create_directory",
        }
        candidates: list[tuple[str, str]] = []
        if tool_name in tools_with_root_arg:
            for key in ("path", "paths", "source", "dest", "root"):
                val = args.get(key)
                if isinstance(val, str) and val.strip():
                    candidates.append((key, val.strip()))
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, str) and item.strip():
                            candidates.append((key, item.strip()))
        return candidates


