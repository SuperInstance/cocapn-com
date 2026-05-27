"""MessageRouter — route messages between agents with rules and filtering."""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Callable

from .channel import Channel, ChannelMode
from .message import Message, MessageType

logger = logging.getLogger(__name__)

# A filter returns True when the message should be accepted.
MessageFilter = Callable[[Message], bool]


@dataclass
class DeliveryRule:
    """A rule that governs how a message is routed.

    Attributes:
        source_pattern: Glob pattern matched against ``message.sender``.
        dest_pattern: Glob pattern matched against ``message.recipient``.
        types: If non-empty, only these message types are forwarded.
        channel_name: Target channel to deliver to. If ``None`` the router
            picks the default channel matching the recipient.
        filter_fn: Optional callable for custom filtering logic.
        forward_to: Additional agent IDs to forward matching messages to.
        enabled: Set to ``False`` to disable the rule without removing it.
    """

    source_pattern: str = "*"
    dest_pattern: str = "*"
    types: list[MessageType] = field(default_factory=list)
    channel_name: str | None = None
    filter_fn: MessageFilter | None = None
    forward_to: list[str] = field(default_factory=list)
    enabled: bool = True

    def matches(self, message: Message) -> bool:
        """Return True if *message* satisfies this rule."""
        if not self.enabled:
            return False

        if not fnmatch.fnmatch(message.sender, self.source_pattern):
            return False

        recipient = message.recipient or "*"
        if not fnmatch.fnmatch(recipient, self.dest_pattern):
            return False

        if self.types and message.type not in self.types:
            return False

        if self.filter_fn and not self.filter_fn(message):
            return False

        return True


class MessageRouter:
    """Central router that dispatches messages through channels.

    The router maintains a registry of channels and a set of delivery
    rules.  When a message is submitted it:

    1. Applies all matching rules to determine forwarding destinations.
    2. Delivers the message via the appropriate channel(s).
    """

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}
        self._rules: list[DeliveryRule] = []
        self._default_channel = Channel("default", ChannelMode.PUB_SUB)
        self._channels["default"] = self._default_channel

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def add_channel(self, channel: Channel) -> None:
        """Register a channel with the router."""
        self._channels[channel.name] = channel
        logger.info("Channel %s added to router", channel.name)

    def get_channel(self, name: str) -> Channel | None:
        return self._channels.get(name)

    def remove_channel(self, name: str) -> None:
        if name == "default":
            raise ValueError("Cannot remove the default channel")
        self._channels.pop(name, None)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: DeliveryRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule: DeliveryRule) -> None:
        self._rules = [r for r in self._rules if r is not rule]

    def clear_rules(self) -> None:
        self._rules.clear()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, message: Message) -> dict[str, list[str]]:
        """Route *message* through matching channels.

        Returns a mapping of ``channel_name -> [agent_ids delivered]``.
        """
        results: dict[str, list[str]] = {}
        matched = False

        for rule in self._rules:
            if rule.matches(message):
                matched = True
                # Forward to specified channel
                if rule.channel_name:
                    ch = self._channels.get(rule.channel_name)
                    if ch:
                        delivered = ch.deliver(message)
                        results[ch.name] = delivered
                # Forward to additional agents via default channel
                if rule.forward_to:
                    for agent_id in rule.forward_to:
                        forwarded = Message(
                            sender=message.sender,
                            recipient=agent_id,
                            payload=message.payload,
                            type=message.type,
                            priority=message.priority,
                            correlation_id=message.id,
                        )
                        delivered = self._default_channel.deliver(forwarded)
                        results.setdefault("default", []).extend(delivered)

        if not matched:
            delivered = self._default_channel.deliver(message)
            results["default"] = delivered

        return results
