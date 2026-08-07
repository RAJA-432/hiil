from __future__ import annotations

import pytest

from mcp_cli.services.frontier import is_sensitive_tool


@pytest.mark.parametrize(
    "name",
    [
        "shell",
        "bash",
        "exec_command",
        "execute_python",
        "system_info",
        "rm",
        "rm_rf",
        "delete_file",
        "remove_file",
        "write_to_system",
        "write_file",
        "edit_document",
        "create_directory",
        "move_file",
        "copy_file",
        "mcp__filesystem__write_file",
    ],
)
def test_sensitive_tools_are_flagged(name):
    assert is_sensitive_tool(name)


@pytest.mark.parametrize(
    "name",
    [
        "get_weather",
        "add_note",
        "get_additional_details",
        "get_file_info",
        "read_file",
        "read_text_resource",
        "search_files",
        "list_directory",
        "calculate_quote",
        "mark_step_done",
        "get_playbook_status",
        "metadata",
        "updater",
        "customer",
        "put_cream",
    ],
)
def test_benign_tools_are_not_flagged(name):
    assert not is_sensitive_tool(name)


def test_case_insensitive():
    assert is_sensitive_tool("Write_File")
    assert not is_sensitive_tool("GET_Weather")
