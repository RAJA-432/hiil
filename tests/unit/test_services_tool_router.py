from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_cli.services.tool_router import ToolRouter


def _make_tool_entry(name: str, client: MagicMock, description: str = "test tool") -> dict:
    return {
        "client": client,
        "openai": {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": {}},
            },
        },
    }


def _make_client(server_id: str, script: str = "") -> MagicMock:
    client = MagicMock()
    client.script = script
    client.call_tool = AsyncMock(return_value=f"result from {server_id}")
    return client


def test_constructor_filters_tools_by_capability():
    fs_client = _make_client("filesystem", "filesystem_server.py")
    chat_client = _make_client("chat", "chat_server.py")
    tools = {
        "read_file": _make_tool_entry("read_file", fs_client),
        "write_file": _make_tool_entry("write_file", fs_client),
        "send_message": _make_tool_entry("send_message", chat_client),
    }
    clients = {"filesystem": fs_client, "chat": chat_client}

    router = ToolRouter(tools, clients, capabilities=["filesystem"])
    assert "read_file" in router._allowed
    assert "write_file" in router._allowed
    assert "send_message" not in router._allowed


def test_openai_tools_property():
    client = _make_client("fs")
    tools = {
        "read_file": _make_tool_entry("read_file", client),
        "write_file": _make_tool_entry("write_file", client),
    }
    router = ToolRouter(tools, {"fs": client}, capabilities=["fs"])

    result = router.openai_tools
    assert len(result) == 2
    assert all(t["type"] == "function" for t in result)
    names = {t["function"]["name"] for t in result}
    assert names == {"read_file", "write_file"}


def test_tool_names_property():
    client = _make_client("fs")
    tools = {"read_file": _make_tool_entry("read_file", client)}
    router = ToolRouter(tools, {"fs": client}, capabilities=["fs"])
    assert router.tool_names == ["read_file"]


@pytest.mark.asyncio
async def test_call_tool_allowed():
    client = _make_client("fs")
    tools = {"read_file": _make_tool_entry("read_file", client)}
    router = ToolRouter(tools, {"fs": client}, capabilities=["fs"])

    result = await router.call_tool("read_file", {"path": "/test"})
    client.call_tool.assert_awaited_once_with("read_file", {"path": "/test"})
    assert result == "result from fs"


@pytest.mark.asyncio
async def test_call_tool_denied():
    client = _make_client("fs")
    tools = {"read_file": _make_tool_entry("read_file", client)}
    router = ToolRouter(tools, {"fs": client}, capabilities=["fs"])

    result = await router.call_tool("send_message", {"text": "hi"})
    assert "[denied]" in result
    assert "send_message" in result


@pytest.mark.asyncio
async def test_call_tool_unknown():
    client = _make_client("fs")
    tools = {"read_file": _make_tool_entry("read_file", client)}
    router = ToolRouter(tools, {"fs": client}, capabilities=["fs"])

    result = await router.call_tool("nonexistent", {})
    assert "[denied]" in result


def test_explicit_capability_map():
    client = _make_client("generic", "generic_server.py")
    tools = {"read_file": _make_tool_entry("read_file", client)}

    router = ToolRouter(
        tools, {"generic": client},
        capabilities=["filesystem"],
        tool_capability_map={"read_file": "filesystem"},
    )
    assert "read_file" in router._allowed


def test_explicit_map_overrides_server_cap():
    fs_client = _make_client("fs")
    tools = {"read_file": _make_tool_entry("read_file", fs_client)}

    router = ToolRouter(
        tools, {"fs": fs_client},
        capabilities=["chat"],
        tool_capability_map={"read_file": "chat"},
    )
    assert "read_file" in router._allowed


def test_tool_name_prefix_matching():
    client = _make_client("misc")
    tools = {
        "filesystem_read": _make_tool_entry("filesystem_read", client),
        "filesystem_write": _make_tool_entry("filesystem_write", client),
        "chat_send": _make_tool_entry("chat_send", client),
    }

    router = ToolRouter(tools, {"misc": client}, capabilities=["filesystem"])
    assert "filesystem_read" in router._allowed
    assert "filesystem_write" in router._allowed
    assert "chat_send" not in router._allowed


def test_tool_name_prefix_matching_without_underscore():
    client = _make_client("misc")
    tools = {
        "filesystem": _make_tool_entry("filesystem", client),
    }
    router = ToolRouter(tools, {"misc": client}, capabilities=["filesystem"])
    assert "filesystem" in router._allowed


def test_server_id_capability_fallback():
    client = _make_client("github")
    tools = {"list_issues": _make_tool_entry("list_issues", client)}
    router = ToolRouter(tools, {"github": client}, capabilities=["github"])
    assert "list_issues" in router._allowed


def test_server_script_based_tags():
    client = _make_client("doc_client", "document_server.py")
    tools = {"read_document": _make_tool_entry("read_document", client)}
    router = ToolRouter(tools, {"doc_client": client}, capabilities=["document"])
    assert "read_document" in router._allowed


def test_build_server_cap_index_includes_doc_client_fallback():
    router = ToolRouter({}, {}, capabilities=[])
    assert "doc_client" in router._server_caps
    assert "doc" in router._server_caps["doc_client"]


def test_doc_client_not_overwritten():
    client = _make_client("doc_client", "custom_doc.py")
    router = ToolRouter({}, {"doc_client": client}, capabilities=[])
    caps = router._server_caps["doc_client"]
    assert "custom" in caps
    assert "doc" in caps  # derived from script name parts


def test_refresh_rebuilds_allowed():
    client_fs = _make_client("fs")
    client_chat = _make_client("chat")
    tools = {
        "read_file": _make_tool_entry("read_file", client_fs),
        "send": _make_tool_entry("send", client_chat),
    }
    clients = {"fs": client_fs, "chat": client_chat}

    router = ToolRouter(tools, clients, capabilities=["fs"])
    assert "read_file" in router._allowed
    assert "send" not in router._allowed

    router._capabilities = ["chat"]
    router.refresh()
    assert "read_file" not in router._allowed
    assert "send" in router._allowed


def test_empty_capabilities_allows_nothing():
    client = _make_client("fs")
    tools = {"read_file": _make_tool_entry("read_file", client)}
    router = ToolRouter(tools, {"fs": client}, capabilities=[])
    assert len(router._allowed) == 0


def test_empty_tools():
    router = ToolRouter({}, {}, capabilities=["fs"])
    assert router.openai_tools == []
    assert router.tool_names == []
