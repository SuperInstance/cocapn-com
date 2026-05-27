"""Channel — the medium over which agents communicate."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable

from .message import Message

logger = logging.getLogger(__name__)

# Type alias for message handlers — can be sync or async.
MessageHandler = Callable[[Message], Awaitable[None] | None]


class ChannelMode(str, Enum):
    """Supported channel modes."""

    PUB_SUB = "pub_sub"
    POINT_TO_POINT = "point_to_point"
    BROADCAST = "broadcast"


@dataclass
class Channel:
    """A named communication channel that routes messages to subscribers.

    Supports three modes:
    - **PUB_SUB**: every subscriber receives every message.
    - **POINT_TO_POINT**: only the named recipient receives the message.
    - **BROADCAST**: messages are delivered to all subscribers regardless
      of the ``recipient`` field.
    """

    name: str
    mode: ChannelMode = ChannelMode.PUB_SUB
    _subscribers: dict[str, list[MessageHandler]] = field(
        default_factory=lambda: defaultdict(list), repr=False
    )

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, agent_id: str, handler: MessageHandler) -> None:
        """Register *handler* for *agent_id* on this channel."""
        self._subscribers[agent_id].append(handler)
        logger.debug("Agent %s subscribed to channel %s", agent_id, self.name)

    def unsubscribe(self, agent_id: str) -> None:
        """Remove all handlers for *agent_id*."""
        self._subscribers.pop(agent_id, None)
        logger.debug("Agent %s unsubscribed from channel %s", agent_id, self.name)

    # ------------------------------------------------------------------
    # Message delivery
    # ------------------------------------------------------------------

    def deliver(self, message: Message) -> list[str]:
        """Deliver *message* according to the channel mode.

        Returns a list of agent IDs that received the message.
        """
        if self.mode == ChannelMode.BROADCAST:
            return self._deliver_to_all(message)

        if self.mode == ChannelMode.POINT_TO_POINT:
            if message.recipient is None:
                logger.warning("Point-to-point channel %s: message has no recipient", self.name)
                return []
            return self._deliver_to(message, [message.recipient])

        # PUB_SUB — everyone gets it
        return self._deliver_to_all(message)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _deliver_to_all(self, message: Message) -> list[str]:
        agent_ids = list(self._subscribers.keys())
        return self._deliver_to(message, agent_ids)

    def _deliver_to(self, message: Message, agent_ids: list[str]) -> list[str]:
        delivered: list[str] = []
        for agent_id in agent_ids:
            handlers = self._subscribers.get(agent_id, [])
            for handler in handlers:
                try:
                    result = handler(message)
                    if asyncio.iscoroutine(result):
                        # Schedule coroutine if inside an event loop
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(result)
                        except RuntimeError:
                            asyncio.run(result)
                except Exception:
                    logger.exception(
                        "Handler error delivering to %s on channel %s",
                        agent_id,
                        self.name,
                    )
            delivered.append(agent_id)
        return delivered

    @property
    def subscriber_count(self) -> int:
        """Number of agents subscribed to this channel."""
        return len(self._subscribers)
