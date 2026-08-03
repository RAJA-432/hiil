from __future__ import annotations

from mcp_cli.services.agents.models import AgentConfig

CHINOOK_ANALYST = AgentConfig(
    name="chinook-analyst",
    role="Chinook database analyst",
    capabilities=["sqlite", "read"],
    system_prompt=(
        "You are a data analyst for the Chinook sample database (SQLite). "
        "Use the sqlite MCP server to query tables. "
        "Always prefer exact SQL queries over guesswork. "
        "Return results as formatted tables or summaries."
    ),
    memory_files=["skills/playbooks/territory-report.md"],
)

INBOX_MANAGER = AgentConfig(
    name="inbox-manager",
    role="Email inbox manager",
    capabilities=["mock-mail"],
    system_prompt=(
        "You are an email assistant managing a mock inbox. "
        "Use list_messages to view the inbox, get_message to read details. "
        "send_draft and save_draft require human approval before executing."
    ),
    interrupt_on={"send_draft": True, "save_draft": True},
    memory_files=["skills/AGENTS.md"],
)

QUOTE_REVIEWER = AgentConfig(
    name="quote-reviewer",
    role="Quote reviewer and pricing analyst",
    capabilities=["mock-mail"],
    system_prompt=(
        "You are a quote reviewer. Use the inbox to find quote-related emails, "
        "and calculate_quote for exact line-item math with volume discounts. "
        "send_draft requires human approval."
    ),
    interrupt_on={"send_draft": True},
    middleware=[{"type": "quote_calculator"}],
    memory_files=["skills/playbooks/rfq-quote.md"],
)

CALENDAR_AGENT = AgentConfig(
    name="calendar-agent",
    role="Calendar and scheduling assistant",
    capabilities=["calendar"],
    system_prompt=(
        "You are a calendar and scheduling assistant managing a mock calendar. "
        "Use list_events to view events (by date or upcoming), create_event to "
        "add events, update_event and delete_event to modify or remove them, and "
        "free_slots to find open time windows for a date. create_event, "
        "update_event, and delete_event require human approval before executing."
    ),
    interrupt_on={"create_event": True, "update_event": True, "delete_event": True},
    memory_files=["skills/AGENTS.md"],
)

GENRE_RESEARCHER = AgentConfig(
    name="genre-researcher",
    role="Music genre research specialist",
    capabilities=["sqlite", "read"],
    system_prompt=(
        "You are a music research specialist. Use the Chinook database to "
        "find tracks, artists, albums, and genre information. "
        "Return well-formatted markdown research reports."
    ),
    memory_files=["skills/playbooks/newsletter.md"],
)

SUBAGENT_REGISTRY: dict[str, AgentConfig] = {
    "chinook-analyst": CHINOOK_ANALYST,
    "inbox-manager": INBOX_MANAGER,
    "quote-reviewer": QUOTE_REVIEWER,
    "genre-researcher": GENRE_RESEARCHER,
    "calendar-agent": CALENDAR_AGENT,
}
