"""
Mock Calendar MCP Server — local development mock of an enterprise calendar service.

Provides: list_events, create_event, update_event, delete_event, free_slots.
Events are stored per user in a JSON file at ``~/.hiil/store/calendar.json``
(override the path with the ``HIIL_CALENDAR_STORE`` env var). No external
credentials are required.

Run directly:
    python -m setu_bridge.calendar                           # stdio (default)
    python -m setu_bridge.calendar --transport sse --port 8300
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calendar")

_DEFAULT_STORE = Path.home() / ".hiil" / "store" / "calendar.json"


# ---------------------------------------------------------------------------
# Store — in-memory calendar persisted to a JSON file
# ---------------------------------------------------------------------------


class _CalendarStore:
    """Per-user event store backed by a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = Path(os.environ.get("HIIL_CALENDAR_STORE") or _DEFAULT_STORE)
        self._path = Path(path)
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = raw
        except (OSError, ValueError):
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, self._path)

    def events_for(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._data.get(user_id, []))

    def get_event(self, user_id: str, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            for ev in self._data.get(user_id, []):
                if ev["id"] == event_id:
                    return dict(ev)
            return None

    def add_event(self, user_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault(user_id, []).append(event)
            self._save()

    def update_event(self, user_id: str, event_id: str, **changes: Any) -> dict[str, Any] | None:
        with self._lock:
            for ev in self._data.get(user_id, []):
                if ev["id"] == event_id:
                    ev.update(changes)
                    self._save()
                    return dict(ev)
            return None

    def delete_event(self, user_id: str, event_id: str) -> bool:
        with self._lock:
            events = self._data.get(user_id, [])
            for i, ev in enumerate(events):
                if ev["id"] == event_id:
                    events.pop(i)
                    self._save()
                    return True
            return False


_store = _CalendarStore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_id(u: str) -> str:
    return u if u != "default" else os.environ.get("HIIL_USER_ID", "default")


def _parse_date(date: str) -> datetime:
    try:
        return datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date '{date}'. Expected ISO format YYYY-MM-DD (e.g. 2026-08-03)."
        ) from None


def _parse_time(time: str) -> datetime:
    try:
        return datetime.strptime(time, "%H:%M")
    except ValueError:
        raise ValueError(
            f"Invalid time '{time}'. Expected 24-hour HH:MM format (e.g. 14:30)."
        ) from None


def _time_to_min(t: datetime) -> int:
    return t.hour * 60 + t.minute


def _min_to_time(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_events(date: str | None = None, user_id: str = "default") -> str:
    """List calendar events for a date (ISO ``YYYY-MM-DD``) or all upcoming if none.

    Args:
        date: Optional ISO date ``YYYY-MM-DD``. When omitted, all upcoming
            events (today or later) are listed.
        user_id: Owner of the events (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    events = _store.events_for(uid)
    if date is not None:
        _parse_date(date)
        events = [e for e in events if e["date"] == date]
    else:
        today = datetime.now().date().isoformat()
        events = [e for e in events if e["date"] >= today]
    events.sort(key=lambda e: (e["date"], e["start_time"]))
    return json.dumps({"user_id": uid, "count": len(events), "events": events}, indent=2)


@mcp.tool()
async def create_event(
    title: str,
    date: str,
    start_time: str = "09:00",
    duration_min: int = 60,
    location: str = "",
    user_id: str = "default",
) -> str:
    """Create a new calendar event.

    Args:
        title: Event title.
        date: ISO date ``YYYY-MM-DD``.
        start_time: 24-hour start time ``HH:MM``.
        duration_min: Duration in minutes (positive integer).
        location: Optional location string.
        user_id: Owner of the event (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    _parse_date(date)
    _parse_time(start_time)
    if not title or not title.strip():
        raise ValueError("Event title must not be empty.")
    if duration_min <= 0:
        raise ValueError(f"Invalid duration_min '{duration_min}'. Must be a positive number of minutes.")
    event = {
        "id": f"event_{uuid.uuid4().hex[:8]}",
        "title": title.strip(),
        "date": _parse_date(date).strftime("%Y-%m-%d"),
        "start_time": start_time,
        "duration_min": int(duration_min),
        "location": location,
        "user_id": uid,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _store.add_event(uid, event)
    return json.dumps({"status": "created", "event": event}, indent=2)


@mcp.tool()
async def update_event(
    event_id: str,
    title: str | None = None,
    date: str | None = None,
    start_time: str | None = None,
    duration_min: int | None = None,
    location: str | None = None,
    user_id: str = "default",
) -> str:
    """Update fields on an existing event. Only provided fields are changed.

    Args:
        event_id: The event ID (e.g. ``event_a1b2c3d4``).
        title: New title.
        date: New ISO date ``YYYY-MM-DD``.
        start_time: New 24-hour start time ``HH:MM``.
        duration_min: New duration in minutes (positive integer).
        location: New location.
        user_id: Owner of the event (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    changes: dict[str, Any] = {}
    if title is not None:
        if not title.strip():
            raise ValueError("Event title must not be empty.")
        changes["title"] = title.strip()
    if date is not None:
        _parse_date(date)
        changes["date"] = date
    if start_time is not None:
        _parse_time(start_time)
        changes["start_time"] = start_time
    if duration_min is not None:
        if duration_min <= 0:
            raise ValueError(
                f"Invalid duration_min '{duration_min}'. Must be a positive number of minutes."
            )
        changes["duration_min"] = int(duration_min)
    if location is not None:
        changes["location"] = location
    if not changes:
        raise ValueError("No fields provided to update.")
    updated = _store.update_event(uid, event_id, **changes)
    if updated is None:
        return json.dumps({"error": f"Event '{event_id}' not found for user '{uid}'."})
    return json.dumps({"status": "updated", "event": updated}, indent=2)


@mcp.tool()
async def delete_event(event_id: str, user_id: str = "default") -> str:
    """Delete a calendar event by ID.

    Args:
        event_id: The event ID (e.g. ``event_a1b2c3d4``).
        user_id: Owner of the event (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    if _store.delete_event(uid, event_id):
        return json.dumps({"status": "deleted", "event_id": event_id})
    return json.dumps({"error": f"Event '{event_id}' not found for user '{uid}'."})


@mcp.tool()
async def free_slots(
    date: str,
    from_time: str = "09:00",
    to_time: str = "18:00",
    duration_min: int = 60,
    user_id: str = "default",
) -> str:
    """Find open time windows on a date that do not overlap existing events.

    Args:
        date: ISO date ``YYYY-MM-DD``.
        from_time: Start of the search window (24-hour ``HH:MM``).
        to_time: End of the search window (24-hour ``HH:MM``).
        duration_min: Minimum slot length in minutes.
        user_id: Owner of the events (defaults to ``HIIL_USER_ID``).
    """
    uid = _user_id(user_id)
    _parse_date(date)
    from_min = _time_to_min(_parse_time(from_time))
    to_min = _time_to_min(_parse_time(to_time))
    if to_min <= from_min:
        raise ValueError(
            f"Invalid range: to_time '{to_time}' must be later than from_time '{from_time}'."
        )
    if duration_min <= 0:
        raise ValueError(f"Invalid duration_min '{duration_min}'. Must be a positive number of minutes.")

    busy: list[tuple[int, int]] = []
    for ev in _store.events_for(uid):
        if ev["date"] != date:
            continue
        start = _time_to_min(_parse_time(ev["start_time"]))
        busy.append((start, start + int(ev["duration_min"])))
    busy.sort()

    merged: list[tuple[int, int]] = []
    for start, end in busy:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    windows: list[tuple[int, int]] = []
    cursor = from_min
    for start, end in merged:
        if start > cursor and start - cursor >= duration_min:
            windows.append((cursor, start))
        cursor = max(cursor, end)
    if to_min - cursor >= duration_min:
        windows.append((cursor, to_min))

    lines = [
        f"Free slots for {date} ({from_time}-{to_time}, {duration_min} min):",
    ]
    if windows:
        lines.extend(f"- {_min_to_time(s)} - {_min_to_time(e)}" for s, e in windows)
    else:
        lines.append("- none")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock Calendar MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8300)
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
