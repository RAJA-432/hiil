from __future__ import annotations

from vajra_gate.models import ChatRequest, KaryaRequest


def test_chat_request_defaults():
    req = ChatRequest(message="hello")
    assert req.message == "hello"
    assert req.session_id == "default"


def test_chat_request_custom_session():
    req = ChatRequest(message="hello", session_id="my-session")
    assert req.session_id == "my-session"


def test_tool_call_request_defaults():
    req = KaryaRequest(name="my_tool")
    assert req.name == "my_tool"
    assert req.arguments == {}


def test_tool_call_request_with_args():
    req = KaryaRequest(name="my_tool", arguments={"key": "value"})
    assert req.arguments == {"key": "value"}
