from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from mcp_cli.services.logging import get_logger
from mcp_cli.services.sqlite_store import SqliteStore, asyncify

logger = get_logger(__name__)

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4": (30.0, 60.0),
    "gpt-4-32k": (60.0, 120.0),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-opus": (15.0, 75.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
    "claude-4": (15.0, 75.0),
    "claude-4-sonnet": (15.0, 75.0),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "llama-3.1-70b": (0.59, 0.79),
    "llama-3.1-8b": (0.05, 0.08),
    "qwen-2.5-72b": (0.90, 0.90),
    "mistral-large": (2.0, 6.0),
    "command-r-plus": (3.0, 15.0),
}

def _detect_family(model: str) -> str:
    """Match a model name to a known pricing key by prefix matching."""
    model_lower = model.lower()
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if model_lower.startswith(key):
            return key
    return "gpt-4o"

def count_tokens(text: str | list | dict, model: str = "gpt-4o") -> int:
    """Count tokens in text, content arrays, or dicts.

    Handles OpenAI multimodal content arrays where image_url items cost 85 tokens each.
    """
    if isinstance(text, list):
        total = 0
        for item in text:
            if isinstance(item, dict) and item.get("type") == "image_url":
                total += 85
            elif isinstance(item, dict) and item.get("type") == "text":
                total += count_tokens(item.get("text", ""), model)
            else:
                total += count_tokens(str(item), model)
        return total
    if isinstance(text, dict):
        return count_tokens(json.dumps(text), model)
    try:
        import tiktoken
        encoding_name = _encoding_for_model(model)
        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)

def _encoding_for_model(model: str) -> str:
    m = model.lower()
    if "gpt-4" in m or "gpt-3" in m:
        return "cl100k_base"
    if "text-embedding" in m:
        return "cl100k_base"
    if "davinci" in m or "curie" in m or "babbage" in m or "ada" in m:
        return "p50k_base"
    if "gpt-2" in m:
        return "gpt2"
    return "cl100k_base"

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate the USD cost for a given model and token counts based on known pricing."""
    family = _detect_family(model)
    input_price, output_price = MODEL_PRICING.get(family, (2.50, 10.0))
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return input_cost + output_cost

@dataclass
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: str = ""
    session_id: str = "default"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

class UsageTracker(SqliteStore):
    _SCHEMA = [
        """CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost REAL,
            timestamp TEXT,
            session_id TEXT
        )""",
    ]

    def __init__(self, db_path: str = "chat_history.db"):
        self._session_input: int = 0
        self._session_output: int = 0
        self._session_cost: float = 0.0
        super().__init__(db_path)

    def record(self, model: str, input_tokens: int, output_tokens: int, session_id: str = "default"):
        """Persist a usage record and update the in-memory session counters."""
        cost = estimate_cost(model, input_tokens, output_tokens)
        rec = UsageRecord(model, input_tokens, output_tokens, cost, session_id=session_id)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO usage_log (model, input_tokens, output_tokens, cost, timestamp, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rec.model, rec.input_tokens, rec.output_tokens, rec.cost, rec.timestamp, rec.session_id),
            )
            conn.commit()
        self._session_input += input_tokens
        self._session_output += output_tokens
        self._session_cost += cost

    def session_summary(self) -> dict:
        """Return aggregated token and cost counts for the current session."""
        return {
            "input_tokens": self._session_input,
            "output_tokens": self._session_output,
            "total_tokens": self._session_input + self._session_output,
            "cost": round(self._session_cost, 6),
        }

    def session_summary_for(self, session_id: str) -> dict:
        """Return aggregated token and cost counts for a persisted session."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0), "
            "COALESCE(SUM(cost), 0) FROM usage_log WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        return {
            "input_tokens": row[0],
            "output_tokens": row[1],
            "total_tokens": row[0] + row[1],
            "cost": round(row[2], 6),
        }

    def total_summary(self) -> dict:
        """Return aggregated token and cost counts across all persisted records."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0), "
            "COALESCE(SUM(cost), 0) FROM usage_log"
        )
        row = cursor.fetchone()
        return {
            "input_tokens": row[0],
            "output_tokens": row[1],
            "total_tokens": row[0] + row[1],
            "cost": round(row[2], 6),
        }

    def history(self, limit: int = 20) -> list[dict]:
        """Return the most recent usage records, ordered by timestamp descending."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT model, input_tokens, output_tokens, cost, timestamp, session_id "
            "FROM usage_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "model": row[0],
                "input_tokens": row[1],
                "output_tokens": row[2],
                "cost": row[3],
                "timestamp": row[4],
                "session_id": row[5],
            }
            for row in cursor.fetchall()
        ]

    @asyncify("record")
    async def async_record(self, model: str, input_tokens: int, output_tokens: int, session_id: str = "default"):
        ...

    @asyncify("session_summary_for")
    async def async_session_summary_for(self, session_id: str) -> dict:
        return {}

    @asyncify("total_summary")
    async def async_total_summary(self) -> dict:
        return {}

    @asyncify("history")
    async def async_history(self, limit: int = 20) -> list[dict]:
        return []
