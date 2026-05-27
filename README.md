# cocapn-com

Inter-agent messaging protocols and message routing for the Cocapn fleet.

## Installation

```bash
pip install cocapn-com
```

## Quick Start

### Create and route a message

```python
from cocapn_com import Message, MessageType, Priority, MessageRouter

# Build a message
msg = Message(
    sender="agent-planner",
    recipient="agent-worker",
    payload={"task": "index_documents"},
    type=MessageType.COMMAND,
    priority=Priority.HIGH,
)

# Set up a router with a subscriber
router = MessageRouter()
router._default_channel.subscribe("agent-worker", lambda m: print(f"Got: {m.payload}"))

# Route it
router.route(msg)
# => Got: {'task': 'index_documents'}
```

### Pub/Sub channel

```python
from cocapn_com import Channel, ChannelMode, Message

ch = Channel("events", ChannelMode.PUB_SUB)
ch.subscribe("logger", lambda m: print(f"[LOG] {m.payload}"))
ch.subscribe("auditor", lambda m: print(f"[AUDIT] {m.payload}"))

ch.deliver(Message(sender="svc", recipient=None, payload="user_login"))
# [LOG] user_login
# [AUDIT] user_login
```

### Point-to-point and broadcast

```python
from cocapn_com import Channel, ChannelMode, Message

ptp = Channel("rpc", ChannelMode.POINT_TO_POINT)
ptp.subscribe("db", lambda m: ...)
ptp.subscribe("cache", lambda m: ...)

# Only "db" receives this
ptp.deliver(Message(sender="api", recipient="db", payload="SELECT 1"))
```

### Delivery rules and forwarding

```python
from cocapn_com import MessageRouter, DeliveryRule, Channel, ChannelMode, MessageType

router = MessageRouter()

# Route all ERROR messages to an alerts channel
alerts = Channel("alerts", ChannelMode.PUB_SUB)
alerts.subscribe("ops-team", lambda m: print(f"ALERT: {m.payload}"))
router.add_channel(alerts)

router.add_rule(DeliveryRule(
    types=[MessageType.ERROR],
    channel_name="alerts",
))

# Forward everything to a logger as well
router.add_rule(DeliveryRule(
    forward_to=["logger"],
))
```

### Broker with delivery guarantees

```python
from cocapn_com import MessageBroker, MessageRouter, DeliveryGuarantee, Message

router = MessageRouter()
broker = MessageBroker(router, guarantee=DeliveryGuarantee.AT_LEAST_ONCE)

msg = Message(sender="client", recipient="worker", payload="process_data")
broker.deliver(msg)

# On success, acknowledge
broker.ack(msg.id)

# On failure, nack to retry (up to max_retries, then dead-letter queue)
broker.nack(msg.id)
```

### Protocol framing and handshakes

```python
from cocapn_com import Protocol, Message, HandshakeKind

# Convert a message to a wire frame
msg = Message(sender="a", recipient="b", payload="hello")
frame = Protocol.message_to_frame(msg)
wire_bytes = frame.encode()

# Decode on the other side
decoded_frame = type(frame).decode(wire_bytes)
restored = Protocol.frame_to_message(decoded_frame)

# Handshake between agents
init, init_frame = Protocol.init_handshake(
    "agent-1",
    kind=HandshakeKind.BASIC,
    capabilities=["pub_sub", "rpc"],
)
accept, accept_frame = Protocol.accept_handshake(init, our_capabilities=["pub_sub"])
print(accept.shared_capabilities)  # ['pub_sub']
```

## Architecture

```
cocapn_com/
├── __init__.py      # Public API
├── message.py       # Message, MessageType, Priority
├── channel.py       # Channel with pub/sub, point-to-point, broadcast
├── router.py        # MessageRouter with delivery rules and filtering
├── protocol.py      # Wire framing, handshakes, protocol versioning
└── broker.py        # MessageBroker with queuing, retries, DLQ
```

## Features

- **Message types**: text, command, event, query, response, error, heartbeat, control
- **Priority levels**: low, normal, high, urgent — automatic priority queue ordering
- **Channel modes**: pub/sub, point-to-point, broadcast
- **Delivery rules**: glob patterns on sender/recipient, type filtering, custom filter functions, forwarding
- **Delivery guarantees**: best-effort, at-least-once (with ack/nack), exactly-once (deduplication)
- **Protocol framing**: encode/decode with type+length+payload wire format
- **Handshakes**: basic, authenticated, encrypted negotiation with capability matching
- **Dead-letter queue**: automatic expiry, retry exhaustion, configurable callbacks
- **Zero external dependencies**: only stdlib + pytest for testing

## License

MIT © SuperInstance
