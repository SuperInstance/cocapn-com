"""MessageBroker — queuing, priority ordering, and delivery guarantees."""

from __future__ import annotations

import heapq
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .message import Message, MessageType, Priority
from .router import MessageRouter

logger = logging.getLogger(__name__)


class DeliveryGuarantee(str, Enum):
    """Quality-of-service levels for message delivery."""

    BEST_EFFORT = "best_effort"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass(order=True)
class _PrioritizedMessage:
    """Wrapper so messages are ordered by (-priority, timestamp) in the heap."""

    sort_key: tuple[int, float] = field(compare=True)
    message: Message = field(compare=False)

    @classmethod
    def wrap(cls, msg: Message) -> _PrioritizedMessage:
        # Higher priority value = more urgent, so negate for min-heap
        return cls(sort_key=(-msg.priority.value, msg.timestamp), message=msg)


@dataclass
class _PendingAck:
    """Tracks an unacknowledged message for at-least-once delivery."""

    message: Message
    sent_at: float = field(default_factory=time.time)
    attempts: int = 1


class MessageBroker:
    """A broker that queues messages, orders by priority, and manages delivery.

    Features:
    - Per-agent queues with priority ordering.
    - Configurable delivery guarantees (best-effort, at-least-once, exactly-once).
    - Retry logic for unacknowledged messages.
    - Dead-letter queue for expired or undeliverable messages.
    """

    def __init__(
        self,
        router: MessageRouter,
        *,
        guarantee: DeliveryGuarantee = DeliveryGuarantee.BEST_EFFORT,
        max_retries: int = 3,
        retry_interval: float = 5.0,
        dlq_max_size: int = 1000,
    ) -> None:
        self.router = router
        self.guarantee = guarantee
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.dlq_max_size = dlq_max_size

        # Per-recipient priority queues
        self._queues: dict[str, list[_PrioritizedMessage]] = defaultdict(list)
        # Tracking for ack-based guarantees
        self._pending: dict[str, _PendingAck] = {}
        # Exactly-once deduplication set
        self._delivered_ids: set[str] = set()
        # Dead-letter queue
        self._dlq: list[Message] = []
        # Lock for thread safety
        self._lock = threading.Lock()
        # Optional hook called when a message lands in the DLQ
        self.on_dead_letter: Callable[[Message], None] | None = None

    # ------------------------------------------------------------------
    # Enqueue / dequeue
    # ------------------------------------------------------------------

    def enqueue(self, message: Message) -> None:
        """Add a message to the appropriate queue."""
        if message.is_expired():
            self._send_to_dlq(message)
            return

        # Exactly-once: skip duplicates
        if self.guarantee == DeliveryGuarantee.EXACTLY_ONCE:
            if message.id in self._delivered_ids:
                logger.debug("Dropping duplicate message %s", message.id)
                return
            self._delivered_ids.add(message.id)

        with self._lock:
            recipient = message.recipient or "__broadcast__"
            heapq.heappush(self._queues[recipient], _PrioritizedMessage.wrap(message))

    def dequeue(self, recipient: str, *, count: int = 1) -> list[Message]:
        """Pop up to *count* messages for *recipient*, ordered by priority."""
        messages: list[Message] = []
        with self._lock:
            queue = self._queues.get(recipient, [])
            while queue and len(messages) < count:
                item = heapq.heappop(queue)
                msg = item.message
                if msg.is_expired():
                    self._send_to_dlq(msg)
                    continue
                messages.append(msg)
        return messages

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def deliver(self, message: Message) -> dict[str, list[str]]:
        """Enqueue a message and immediately attempt delivery via the router."""
        # Exactly-once early exit (enqueue also checks, but route must be guarded)
        if (
            self.guarantee == DeliveryGuarantee.EXACTLY_ONCE
            and message.id in self._delivered_ids
        ):
            return {}
        self.enqueue(message)
        results = self.router.route(message)

        # Track for delivery guarantees
        if self.guarantee in (
            DeliveryGuarantee.AT_LEAST_ONCE,
            DeliveryGuarantee.EXACTLY_ONCE,
        ):
            self._pending[message.id] = _PendingAck(message=message)

        return results

    def ack(self, message_id: str) -> None:
        """Acknowledge successful delivery of a message."""
        self._pending.pop(message_id, None)

    def nack(self, message_id: str) -> None:
        """Negatively acknowledge — the message should be retried."""
        pending = self._pending.get(message_id)
        if pending is None:
            return
        pending.attempts += 1
        if pending.attempts > self.max_retries:
            self._pending.pop(message_id, None)
            self._send_to_dlq(pending.message)
        else:
            pending.sent_at = time.time()
            self.router.route(pending.message)

    def retry_pending(self) -> int:
        """Re-deliver all pending messages that have exceeded the retry interval.

        Returns the number of messages retried.
        """
        now = time.time()
        retried = 0
        to_retry: list[_PendingAck] = []
        for mid, pending in list(self._pending.items()):
            if (now - pending.sent_at) > self.retry_interval:
                to_retry.append(pending)
        for pending in to_retry:
            self.nack(pending.message.id)
            retried += 1
        return retried

    # ------------------------------------------------------------------
    # Dead-letter queue
    # ------------------------------------------------------------------

    def _send_to_dlq(self, message: Message) -> None:
        if len(self._dlq) >= self.dlq_max_size:
            self._dlq.pop(0)
        self._dlq.append(message)
        logger.warning("Message %s sent to DLQ", message.id)
        if self.on_dead_letter:
            self.on_dead_letter(message)

    @property
    def dead_letters(self) -> list[Message]:
        return list(self._dlq)

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def queue_size(self, recipient: str) -> int:
        return len(self._queues.get(recipient, []))

    def pending_count(self) -> int:
        return len(self._pending)

    def flush(self) -> None:
        """Clear all queues and pending state."""
        with self._lock:
            self._queues.clear()
            self._pending.clear()
            self._delivered_ids.clear()
