"""
A2A (Agent-to-Agent) — simple protocol for agents to discover and
communicate with each other via an in-memory message bus.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class A2AAgent:
    id: str
    name: str
    role: str
    capabilities: list[str] = field(default_factory=list)
    registered_at: float = 0.0
    last_seen: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
        }


@dataclass
class A2AMessage:
    id: str
    sender_id: str
    recipient_id: str
    content: str
    thread_id: str | None = None
    created_at: float = 0.0
    read: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "content": self.content[:200],
            "thread_id": self.thread_id,
            "created_at": self.created_at,
            "read": self.read,
        }


class A2ABus:
    """In-memory pub-sub for agent-to-agent messages."""

    def __init__(self):
        self._agents: dict[str, A2AAgent] = {}
        self._messages: list[A2AMessage] = []

    def register(self, name: str, role: str,
                 capabilities: list[str] | None = None) -> A2AAgent:
        now = time.time()
        agent = A2AAgent(
            id=f"a2a_{uuid.uuid4().hex[:12]}",
            name=name,
            role=role,
            capabilities=capabilities or [],
            registered_at=now,
            last_seen=now,
        )
        self._agents[agent.id] = agent
        return agent

    def unregister(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def heartbeat(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.last_seen = time.time()
        return True

    def discover(self, capability: str | None = None) -> list[A2AAgent]:
        agents = list(self._agents.values())
        if capability:
            agents = [a for a in agents if capability in a.capabilities]
        return agents

    def send(self, sender_id: str, recipient_id: str, content: str,
             thread_id: str | None = None) -> A2AMessage:
        msg = A2AMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
            thread_id=thread_id,
            created_at=time.time(),
        )
        self._messages.append(msg)
        return msg

    def get_messages(self, agent_id: str, unread_only: bool = False,
                     limit: int = 50) -> list[A2AMessage]:
        msgs = [m for m in self._messages if m.recipient_id == agent_id]
        if unread_only:
            msgs = [m for m in msgs if not m.read]
        msgs.sort(key=lambda m: m.created_at, reverse=True)
        return msgs[:limit]

    def mark_read(self, message_id: str) -> bool:
        for m in self._messages:
            if m.id == message_id:
                m.read = True
                return True
        return False

    def get_agent(self, agent_id: str) -> A2AAgent | None:
        return self._agents.get(agent_id)


_GLOBAL_A2A = A2ABus()


def get_a2a_bus() -> A2ABus:
    return _GLOBAL_A2A
