from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_START_TIME = time.time()

_counts: dict[tuple[str, str, str], int] = defaultdict(int)  # (method, path, status)
_paths: set[str] = set()
_MAX_PATHS = 1000
_chat_total: int = 0
_agent_runs: int = 0
_validation_errors_total: int = 0
_lock = Lock()


def inc_validation_error(skill_id: str = "unknown") -> None:
    global _validation_errors_total
    with _lock:
        _validation_errors_total += 1


def inc_request(method: str, path: str, status: int) -> None:
    with _lock:
        if path not in _paths:
            if len(_paths) >= _MAX_PATHS:
                path = "other"
            else:
                _paths.add(path)
        _counts[(method, path, str(status))] += 1


def inc_chat() -> None:
    global _chat_total
    with _lock:
        _chat_total += 1


def inc_agent_run() -> None:
    global _agent_runs
    with _lock:
        _agent_runs += 1


def generate() -> str:
    lines: list[str] = [
        "# HELP hiil_uptime_seconds Server uptime",
        "# TYPE hiil_uptime_seconds gauge",
        f"hiil_uptime_seconds {time.time() - _START_TIME}",
        "",
        "# HELP hiil_http_requests_total Total HTTP requests",
        "# TYPE hiil_http_requests_total counter",
    ]
    with _lock:
        for (method, path, status), count in sorted(_counts.items()):
            lines.append(
                f'hiil_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
            )

    lines += [
        "",
        "# HELP hiil_chat_messages_total Total chat messages sent",
        "# TYPE hiil_chat_messages_total counter",
        f"hiil_chat_messages_total {_chat_total}",
        "",
        "# HELP hiil_agent_runs_total Total agent runs",
        "# TYPE hiil_agent_runs_total counter",
        f"hiil_agent_runs_total {_agent_runs}",
        "",
        "# HELP hiil_validation_errors_total Total LLM outputs that failed schema validation",
        "# TYPE hiil_validation_errors_total counter",
        f"hiil_validation_errors_total {_validation_errors_total}",
        "",
    ]
    return "\n".join(lines) + "\n"
