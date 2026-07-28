from __future__ import annotations

from mcp_cli.services.agents.permissions import (
    FilesystemPermission,
    PermissionEnforcer,
)


def make_enforcer(*perms):
    return PermissionEnforcer(permissions=list(perms))


class TestPermissionEnforcer:
    def test_allow_operation(self):
        perm = FilesystemPermission(operations=["read"], paths=["/tmp/*"], mode="allow")
        enforcer = make_enforcer(perm)
        assert enforcer.is_operation_allowed("read", "/tmp/foo.txt") is True

    def test_deny_operation(self):
        perm = FilesystemPermission(operations=["write"], paths=["/etc/*"], mode="deny")
        enforcer = make_enforcer(perm)
        assert enforcer.is_operation_allowed("write", "/etc/passwd") is False

    def test_allow_overrides_default(self):
        allow = FilesystemPermission(operations=["read"], paths=["/data/*"], mode="allow")
        enforcer = make_enforcer(allow)
        assert enforcer.is_operation_allowed("read", "/data/file.txt") is True

    def test_no_match_returns_false(self):
        enforcer = make_enforcer()
        assert enforcer.is_operation_allowed("read", "/anything") is False

    def test_first_match_wins(self):
        deny = FilesystemPermission(operations=["read"], paths=["/secret/*"], mode="deny")
        allow = FilesystemPermission(operations=["read"], paths=["/*"], mode="allow")
        enforcer = make_enforcer(deny, allow)
        assert enforcer.is_operation_allowed("read", "/secret/data.txt") is False
        assert enforcer.is_operation_allowed("read", "/public.txt") is True

    def test_enforce_returns_none_when_allowed(self):
        perm = FilesystemPermission(operations=["read"], paths=["/*"], mode="allow")
        enforcer = make_enforcer(perm)
        assert enforcer.enforce("read", "/tmp/x.txt") is None

    def test_enforce_returns_error_when_denied(self):
        enforcer = make_enforcer()
        err = enforcer.enforce("write", "/etc/hosts")
        assert err is not None
        assert "denied" in err

    def test_enforce_includes_tool_name(self):
        enforcer = make_enforcer()
        err = enforcer.enforce("write", "/etc/hosts", tool_name="write_file")
        assert "write_file" in err


class TestInspectToolArgs:
    def test_path_key_checked(self):
        allow = FilesystemPermission(operations=["read"], paths=["/ok/*"], mode="allow")
        enforcer = make_enforcer(allow)
        assert enforcer.inspect_tool_args("read_file", {"path": "/ok/file.txt"}) is None

    def test_path_key_denied(self):
        allow = FilesystemPermission(operations=["read"], paths=["/ok/*"], mode="allow")
        enforcer = make_enforcer(allow)
        err = enforcer.inspect_tool_args("read_file", {"path": "/bad/file.txt"})
        assert err is not None

    def test_paths_list_checked(self):
        allow = FilesystemPermission(operations=["read"], paths=["/safe/*"], mode="allow")
        enforcer = make_enforcer(allow)
        err = enforcer.inspect_tool_args("read_multiple_files", {"paths": ["/safe/a.txt", "/unsafe/b.txt"]})
        assert err is not None

    def test_paths_list_all_allowed(self):
        allow = FilesystemPermission(operations=["read"], paths=["/*"], mode="allow")
        enforcer = make_enforcer(allow)
        assert enforcer.inspect_tool_args("read_multiple_files", {"paths": ["/a.txt", "/b.txt"]}) is None

    def test_source_dest_keys_checked_for_write_tools(self):
        allow = FilesystemPermission(operations=["write"], paths=["/out/*"], mode="allow")
        enforcer = make_enforcer(allow)
        assert enforcer.inspect_tool_args("copy_file", {"source": "/out/a.txt", "dest": "/out/b.txt"}) is None

    def test_write_tool_detected(self):
        deny_write = FilesystemPermission(operations=["write"], paths=["/*"], mode="deny")
        enforcer = make_enforcer(deny_write)
        err = enforcer.inspect_tool_args("write_file", {"path": "/any.txt"})
        assert err is not None

    def test_empty_string_skipped(self):
        enforcer = make_enforcer()
        assert enforcer.inspect_tool_args("read_file", {"path": ""}) is None
