from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Operation = Literal["read", "write", "delete"]

_WRITE_TOOLS = (
    "write_file",
    "edit_file",
    "move_file",
    "copy_file",
    "create_directory",
    "delete_file",
    "delete_directory",
    "mkdir",
    "rmdir",
)


@dataclass
class FilesystemPermission:
    operations: list[Operation]
    paths: list[str]
    mode: Literal["allow", "deny"]


@dataclass
class PermissionEnforcer:
    permissions: list[FilesystemPermission] = field(default_factory=list)

    def is_operation_allowed(self, operation: Operation, path: str) -> bool:
        resolved = Path(path).as_posix()

        for perm in self.permissions:
            if operation not in perm.operations:
                continue
            for pattern in perm.paths:
                if fnmatch.fnmatch(resolved, pattern):
                    if perm.mode == "deny":
                        return False
                    return True

        return False

    def enforce(self, operation: Operation, path: str, tool_name: str = "") -> str | None:
        if self.is_operation_allowed(operation, path):
            return None
        return (
            f"[denied] {operation} on '{path}' is not allowed by agent permissions"
            + (f" for tool '{tool_name}'" if tool_name else "")
        )

    def inspect_tool_args(self, tool_name: str, args: dict) -> str | None:
        path_keys = {"path", "paths", "source", "dest", "root", "target", "filepath", "output_path", "input_path", "directory", "src", "dst", "filename"}
        for key in path_keys:
            val = args.get(key)
            if isinstance(val, str) and val.strip():
                err = self.enforce("write" if tool_name in _WRITE_TOOLS else "read", val.strip(), tool_name)
                if err:
                    return err
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        err = self.enforce("read", item.strip(), tool_name)
                        if err:
                            return err
        for key, val in args.items():
            if key not in path_keys and isinstance(val, str) and val.strip() and ('/' in val or '\\' in val or val.startswith('.')):
                err = self.enforce("write" if tool_name in _WRITE_TOOLS else "read", val.strip(), tool_name)
                if err:
                    return err
        return None
