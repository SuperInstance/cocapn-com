# cocapn-com — Inter-Agent Messaging

**Message routing, channels, handshakes, and delivery guarantees for fleet communication.**

## What This Gives You

- **Typed messages** — text, command, event, query, response, error, heartbeat, control
- **Channels** — pub/sub or point-to-point communication modes between agents
- **Routing** — delivery rules with priority-based routing and pattern matching
- **Protocol** — handshake negotiation and frame types for inter-agent wire format
- **Broker** — at-least-once or exactly-once delivery guarantees
- **Priority levels** — LOW, NORMAL, HIGH, URGENT with automatic queue management

## Quick Start

```bash
pip install cocapn-com
```

```python
from cocapn_com import (
    Message, MessageType, Priority,
    Channel, ChannelMode,
    MessageRouter, DeliveryRule,
    MessageBroker, DeliveryGuarantee
)

# Create a message
msg = Message(
    sender="captain",
    recipient="agent-3",
    msg_type=MessageType.COMMAND,
    payload={"action": "deploy", "service": "api-gateway", "version": "v2"},
    priority=Priority.HIGH,
)

# Route messages
router = MessageRouter()
router.add_rule(DeliveryRule(pattern="deploy.*", target="cicd-agent"))
result = router.route(msg)

# Use channels for group communication
channel = Channel(name="fleet-alerts", mode=ChannelMode.PUB_SUB)
channel.subscribe("agent-1")
channel.subscribe("agent-2")
channel.publish(msg)

# Broker with delivery guarantees
broker = MessageBroker(guarantee=DeliveryGuarantee.AT_LEAST_ONCE)
broker.send(msg)
```

## API Reference

### `Message(sender, recipient, msg_type, payload, priority=NORMAL)`
Typed message with `MessageType` enum and `Priority` levels.

### `Channel(name, mode)`
`ChannelMode.PUB_SUB` or `ChannelMode.POINT_TO_POINT`. Subscribe agents, publish messages.

### `MessageRouter`
Add `DeliveryRule(pattern, target)` entries. Routes messages based on content patterns.

### `Protocol`
Handshake negotiation (`HandshakeKind`) and frame types (`FrameType`) for wire compatibility.

### `MessageBroker(guarantee)`
`DeliveryGuarantee.AT_LEAST_ONCE` or `DeliveryGuarantee.EXACTLY_ONCE`.

## How It Fits

The communication backbone of the [SuperInstance fleet](https://github.com/SuperInstance). Every agent-to-agent message flows through `cocapn-com`.

- **[cocapn](https://github.com/SuperInstance/cocapn)** — Core agent infrastructure
- **[captain](https://github.com/SuperInstance/captain)** — Fleet coordination (dispatches via cocapn-com)
- **[agent-whisper](https://github.com/SuperInstance/agent-whisper)** — Encrypted communication layer
- **[co-captain-git-agent](https://github.com/SuperInstance/co-captain-git-agent)** — Human liaison

## Testing

```bash
pytest tests/
```

## Installation

```bash
pip install cocapn-com
```

Python 3.10+. MIT license.
