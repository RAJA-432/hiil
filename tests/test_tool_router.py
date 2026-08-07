from __future__ import annotations

from mcp_cli.services.tool_router import ToolRouter
from setu_bridge.connection import ManagedConnection

MAIL_TOOLS = ("list_messages", "get_message", "send_draft", "save_draft", "authenticate")
CALENDAR_TOOLS = ("list_events", "create_event", "update_event", "delete_event", "free_slots")
READ_TOOLS = ("read_file", "read_text_resource", "read_document")
SQLITE_TOOLS = ("query", "list_tables", "describe_table")


class _FakeClient:
    def __init__(self, script: str = "") -> None:
        self.script = script

    async def call_tool(self, name: str, args: dict) -> str:
        return f"result from {name}"


def _openai_schema(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"{name} tool",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _make_router(capabilities: list[str], *, mail_script: str = "setu_bridge.mock_mail") -> ToolRouter:
    mail = _FakeClient(script=mail_script)
    calendar = _FakeClient(script="setu_bridge.calendar")
    filesystem = _FakeClient(script="@modelcontextprotocol/server-filesystem")
    sqlite = _FakeClient(script="mcp_sqlite")
    clients = {
        "mock_mail": mail,
        "calendar": calendar,
        "filesystem": filesystem,
        "sqlite": sqlite,
    }
    tools = {}
    for name in MAIL_TOOLS:
        tools[name] = {"client": mail, "openai": _openai_schema(name)}
    for name in CALENDAR_TOOLS:
        tools[name] = {"client": calendar, "openai": _openai_schema(name)}
    for name in READ_TOOLS:
        tools[name] = {"client": filesystem, "openai": _openai_schema(name)}
    for name in SQLITE_TOOLS:
        tools[name] = {"client": sqlite, "openai": _openai_schema(name)}
    return ToolRouter(tools_by_name=tools, clients=clients, capabilities=capabilities)


class TestMailCapabilityNormalization:
    def test_mock_mail_capability_allows_all_mail_tools(self):
        router = _make_router(["mock_mail"])
        assert set(MAIL_TOOLS) <= set(router.tool_names)
        assert {t["function"]["name"] for t in router.openai_tools} == set(MAIL_TOOLS)

    def test_hyphenated_capability_allows_all_mail_tools(self):
        router = _make_router(["mock-mail"])
        assert set(MAIL_TOOLS) <= set(router.tool_names)

    def test_hyphenated_capability_allows_mail_even_with_dash_m_script(self):
        router = _make_router(["mock-mail"], mail_script="-m")
        assert set(MAIL_TOOLS) <= set(router.tool_names)

    def test_weather_capability_disallows_mail_tools(self):
        router = _make_router(["weather"])
        assert not (set(MAIL_TOOLS) & set(router.tool_names))
        assert router.tool_names == []


class TestExistingAgentsNoRegression:
    def test_calendar_agent_still_works(self):
        router = _make_router(["calendar"])
        assert set(CALENDAR_TOOLS) <= set(router.tool_names)

    def test_read_agent_still_works(self):
        router = _make_router(["read"])
        assert set(READ_TOOLS) <= set(router.tool_names)

    def test_sqlite_and_read_agent_still_works(self):
        router = _make_router(["sqlite", "read"])
        assert set(SQLITE_TOOLS) <= set(router.tool_names)
        assert set(READ_TOOLS) <= set(router.tool_names)


class TestManagedConnectionScript:
    def test_module_launch_exposes_module_name(self):
        conn = ManagedConnection(command="python", args=["-m", "setu_bridge.mock_mail"])
        assert conn.script == "setu_bridge.mock_mail"

    def test_module_launch_via_uv_exposes_module_name(self):
        conn = ManagedConnection(command="uv", args=["run", "python", "-m", "setu_bridge.mock_mail"])
        assert conn.script == "setu_bridge.mock_mail"

    def test_plain_script_keeps_first_arg(self):
        conn = ManagedConnection(command="python", args=["setu_bridge/mock_mail.py"])
        assert conn.script == "setu_bridge/mock_mail.py"
