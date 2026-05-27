"""Message definition for inter-agent communication."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    """Kinds of messages agents can exchange."""

    TEXT = "text"
    COMMAND = "command"
    EVENT = "event"
    QUERY = "query"
    RESPONSE = "response"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    CONTROL = "control"


class Priority(int, Enum):
    """Message priority levels."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class Message:
    """A single message exchanged between agents.

    Attributes:
        sender: Identifier of the sending agent.
        recipient: Identifier of the receiving agent, or None for broadcast.
        payload: Arbitrary message content.
        type: The kind of message.
        priority: Delivery priority.
        id: Unique message identifier (auto-generated).
        timestamp: Unix timestamp of creation (auto-set).
        headers: Optional metadata key-value pairs.
        correlation_id: Links responses back to the original query.
        ttl: Time-to-live in seconds; message expires after this.
    """

    sender: str
    recipient: str | None
    payload: Any
    type: MessageType = MessageType.TEXT
    priority: Priority = Priority.NORMAL
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    headers: dict[str, str] = field(default_factory=dict)
    correlation_id: str | None = None
    ttl: float | None = None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def is_expired(self) -> bool:
        """Return True if the message has passed its TTL."""
        if self.ttl is None:
            return False
        return (time.time() - self.timestamp) > self.ttl

    def reply(
        self,
        payload: Any,
        *,
        type: MessageType | None = None,
        priority: Priority | None = None,
    ) -> Message:
        """Create a response message addressed back to the sender."""
        return Message(
            sender=self.recipient or "",
            recipient=self.sender,
            payload=payload,
            type=type or MessageType.RESPONSE,
            priority=priority or self.priority,
            correlation_id=self.id,
            headers=self.headers.copy(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the message to a plain dictionary."""
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "type": self.type.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "headers": self.headers,
            "correlation_id": self.correlation_id,
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Deserialize a message from a dictionary."""
        data = dict(data)  # shallow copy
        if "type" in data and isinstance(data["type"], str):
            data["type"] = MessageType(data["type"])
        if "priority" in data and isinstance(data["priority"], int):
            data["priority"] = Priority(data["priority"])
        return cls(**data)
