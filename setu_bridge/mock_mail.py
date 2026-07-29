"""
Mock Mail MCP Server — local development mock of an enterprise email service.

Provides: list_messages, get_message, send_draft, save_draft.
send_draft and save_draft check an internal auth flag to simulate enterprise
email security policies. The real gating happens at the AgentConfig level
via interrupt_on — this is a defense-in-depth layer.

Run directly:
    python -m setu_bridge.mock_mail                           # stdio (default)
    python -m setu_bridge.mock_mail --transport sse --port 8200
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mock-mail")

# ---------------------------------------------------------------------------
# Mock data — pre-seeded inbox
# ---------------------------------------------------------------------------

_INBOX: list[dict[str, Any]] = [
    {
        "id": "msg_001",
        "from": "vendor@acme-corp.com",
        "to": "procurement@mycompany.com",
        "subject": "Updated pricing for Q3",
        "body": "Hi team,\n\nPlease find attached the updated pricing sheet for Q3. "
                "Volume discounts have been revised for orders over $50,000.\n\n"
                "Best,\nJane\nAcme Corp Sales",
        "folder": "inbox",
        "timestamp": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "read": False,
    },
    {
        "id": "msg_002",
        "from": "support@chinook-db.com",
        "to": "admin@mycompany.com",
        "subject": "Chinook database backup completed",
        "body": "The nightly backup of the Chinook sample database completed successfully.\n"
                "Size: 12.4 MB\nDuration: 3.2 seconds",
        "folder": "inbox",
        "timestamp": (datetime.now(UTC) - timedelta(hours=6)).isoformat(),
        "read": True,
    },
    {
        "id": "msg_003",
        "from": "finance@mycompany.com",
        "to": "procurement@mycompany.com",
        "subject": "Pending quote approvals for this month",
        "body": "Reminder: there are 3 quotes pending approval that exceed $10,000.\n"
                "Please review and approve by end of week.\n\n"
                "Quote IDs: Q-2024-042, Q-2024-043, Q-2024-045",
        "folder": "inbox",
        "timestamp": (datetime.now(UTC) - timedelta(hours=24)).isoformat(),
        "read": False,
    },
    {
        "id": "msg_004",
        "from": "customer@example.com",
        "to": "sales@mycompany.com",
        "subject": "Request for quote — Enterprise license",
        "body": "Hi,\n\nWe are interested in purchasing 50 enterprise licenses "
                "for your platform. Please send a quote with volume pricing.\n\n"
                "Thanks,\nAlex\nExample Corp",
        "folder": "inbox",
        "timestamp": (datetime.now(UTC) - timedelta(hours=48)).isoformat(),
        "read": False,
    },
]

_DRAFTS: list[dict[str, Any]] = []
_AUTH_TOKEN: str | None = None
_MOCK_PASSWORD = "mail_mock_secret"  # noqa: S105


# ---------------------------------------------------------------------------
# Auth helper — simulates enterprise auth without real OAuth
# ---------------------------------------------------------------------------

def _require_auth() -> None:
    if _AUTH_TOKEN is None:
        raise PermissionError(
            "Mail server requires authentication. Call authenticate(password) first."
        )


@mcp.tool()
async def authenticate(password: str) -> str:
    """Authenticate to the mail server.

    Simulates enterprise SMTP/IMAP auth. The password must be
    ``mail_mock_secret`` (for local development only — never hardcoded
    in production).
    """
    if password == _MOCK_PASSWORD:
        global _AUTH_TOKEN
        _AUTH_TOKEN = str(uuid.uuid4())
        return f"Authenticated. Token: {_AUTH_TOKEN[:8]}..."
    return "Authentication failed: invalid password."


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_messages(folder: str = "inbox") -> str:
    """List email messages in a given folder.

    Args:
        folder: Folder name — ``inbox`` or ``drafts``.
    """
    _require_auth()
    if folder == "drafts":
        items = _DRAFTS
    else:
        items = _INBOX

    summary = []
    for msg in items:
        summary.append({
            "id": msg["id"],
            "from": msg["from"],
            "subject": msg["subject"],
            "timestamp": msg["timestamp"],
            "read": msg["read"],
        })
    return json.dumps(summary, indent=2)


@mcp.tool()
async def get_message(message_id: str) -> str:
    """Get the full content of a single email message by ID.

    Args:
        message_id: The message ID (e.g. ``msg_001``).
    """
    _require_auth()
    for msg in _INBOX + _DRAFTS:
        if msg["id"] == message_id:
            msg["read"] = True
            return json.dumps(msg, indent=2)
    return json.dumps({"error": f"Message '{message_id}' not found"})


@mcp.tool()
async def send_draft(to: str, subject: str, body: str) -> str:
    """Send a draft email. (Gated — requires human approval at AgentConfig level.)

    In production this would call an SMTP gateway. In mock mode it
    creates a sent record.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.
    """
    _require_auth()
    msg_id = f"sent_{uuid.uuid4().hex[:8]}"
    record = {
        "id": msg_id,
        "to": to,
        "subject": subject,
        "body": body,
        "status": "sent",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _DRAFTS.append(record)
    return json.dumps({
        "status": "sent",
        "message_id": msg_id,
        "to": to,
        "subject": subject,
    }, indent=2)


@mcp.tool()
async def save_draft(to: str, subject: str, body: str) -> str:
    """Save an email as a draft without sending. (Gated.)

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.
    """
    _require_auth()
    msg_id = f"draft_{uuid.uuid4().hex[:8]}"
    record = {
        "id": msg_id,
        "to": to,
        "subject": subject,
        "body": body,
        "status": "draft",
        "folder": "drafts",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _DRAFTS.append(record)
    return json.dumps({
        "status": "draft_saved",
        "message_id": msg_id,
        "to": to,
        "subject": subject,
    }, indent=2)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock Mail MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8200)
    args = parser.parse_args()
    if args.transport == "sse":
        import uvicorn
        uvicorn.run(mcp.sse_app(), host="127.0.0.1", port=args.port)
    elif args.transport == "streamable-http":
        import uvicorn
        uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
