"""Shared configuration constants for the Setu Bridge MCP servers.

Centralizes values that the individual servers (``mock_mail``,
``connection``) previously hardcoded. Kept intentionally small — only
move a constant here when more than one module could consume it.
"""

# Mock Mail server
MOCK_MAIL_MAX_DRAFTS = 500
MOCK_MAIL_PASSWORD = "mail_mock_secret"  # noqa: S105 -- dev-only mock, not a real credential
MOCK_MAIL_DEFAULT_PORT = 8200

# MCP connection defaults
DEFAULT_CONNECT_TIMEOUT = 30.0
