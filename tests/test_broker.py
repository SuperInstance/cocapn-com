"""Tests for cocapn_com.broker."""

import time

from cocapn_com.broker import DeliveryGuarantee, MessageBroker
from cocapn_com.message import Message, MessageType, Priority
from cocapn_com.router import MessageRouter


def _make_router_with_sub(name: str, received: list):
    router = MessageRouter()
    router._default_channel.subscribe(name, lambda m: received.append(m))
    return router


class TestBrokerEnqueue:
    def test_enqueue_dequeue(self):
        router = MessageRouter()
        broker = MessageBroker(router)
        msg = Message(sender="a", recipient="b", payload="hi")
        broker.enqueue(msg)
        assert broker.queue_size("b") == 1
        msgs = broker.dequeue("b")
        assert len(msgs) == 1
        assert msgs[0].payload == "hi"
        assert broker.queue_size("b") == 0

    def test_priority_ordering(self):
        router = MessageRouter()
        broker = MessageBroker(router)
        low = Message(sender="a", recipient="b", payload="low", priority=Priority.LOW, timestamp=1.0)
        high = Message(sender="a", recipient="b", payload="high", priority=Priority.HIGH, timestamp=2.0)
        urgent = Message(sender="a", recipient="b", payload="urgent", priority=Priority.URGENT, timestamp=3.0)

        broker.enqueue(low)
        broker.enqueue(high)
        broker.enqueue(urgent)

        msgs = broker.dequeue("b", count=3)
        assert [m.payload for m in msgs] == ["urgent", "high", "low"]

    def test_expired_goes_to_dlq(self):
        router = MessageRouter()
        broker = MessageBroker(router)
        msg = Message(sender="a", recipient="b", payload="x", ttl=-1)
        broker.enqueue(msg)
        assert broker.queue_size("b") == 0
        assert len(broker.dead_letters) == 1

    def test_dequeue_skips_expired(self):
        router = MessageRouter()
        broker = MessageBroker(router)
        good = Message(sender="a", recipient="b", payload="good", ttl=9999)
        bad = Message(sender="a", recipient="b", payload="bad", ttl=-1, timestamp=0.0)
        # Insert manually so ordering puts expired first
        from cocapn_com.broker import _PrioritizedMessage
        import heapq
        heapq.heappush(broker._queues["b"], _PrioritizedMessage.wrap(bad))
        heapq.heappush(broker._queues["b"], _PrioritizedMessage.wrap(good))

        msgs = broker.dequeue("b", count=2)
        assert len(msgs) == 1
        assert msgs[0].payload == "good"
        assert len(broker.dead_letters) == 1


class TestBrokerDeliver:
    def test_best_effort(self):
        received: list[Message] = []
        router = _make_router_with_sub("b", received)
        broker = MessageBroker(router, guarantee=DeliveryGuarantee.BEST_EFFORT)

        msg = Message(sender="a", recipient="b", payload="hi")
        broker.deliver(msg)
        assert len(received) == 1
        assert broker.pending_count() == 0

    def test_at_least_once_tracks_pending(self):
        received: list[Message] = []
        router = _make_router_with_sub("b", received)
        broker = MessageBroker(router, guarantee=DeliveryGuarantee.AT_LEAST_ONCE)

        msg = Message(sender="a", recipient="b", payload="hi")
        broker.deliver(msg)
        assert broker.pending_count() == 1

        broker.ack(msg.id)
        assert broker.pending_count() == 0

    def test_exactly_once_dedup(self):
        received: list[Message] = []
        router = _make_router_with_sub("b", received)
        broker = MessageBroker(router, guarantee=DeliveryGuarantee.EXACTLY_ONCE)

        msg = Message(sender="a", recipient="b", payload="hi")
        broker.deliver(msg)
        # Try delivering the same message again
        broker.deliver(msg)
        assert len(received) == 1  # only once


class TestBrokerRetry:
    def test_nack_retries_then_dlq(self):
        received: list[Message] = []
        router = _make_router_with_sub("b", received)
        broker = MessageBroker(
            router,
            guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
            max_retries=2,
        )
        msg = Message(sender="a", recipient="b", payload="hi")
        broker.deliver(msg)

        # nack repeatedly until max retries
        broker.nack(msg.id)
        broker.nack(msg.id)
        broker.nack(msg.id)  # should go to DLQ
        assert len(broker.dead_letters) == 1


class TestBrokerFlush:
    def test_flush_clears_everything(self):
        router = MessageRouter()
        broker = MessageBroker(router, guarantee=DeliveryGuarantee.EXACTLY_ONCE)
        msg = Message(sender="a", recipient="b", payload="hi")
        broker.enqueue(msg)
        broker.deliver(msg)
        broker.flush()
        assert broker.queue_size("b") == 0
        assert broker.pending_count() == 0


class TestBrokerDLQ:
    def test_dlq_callback(self):
        dlq_messages: list[Message] = []
        router = MessageRouter()
        broker = MessageBroker(router)
        broker.on_dead_letter = lambda m: dlq_messages.append(m)

        msg = Message(sender="a", recipient="b", payload="x", ttl=-1)
        broker.enqueue(msg)
        assert len(dlq_messages) == 1

    def test_dlq_max_size(self):
        router = MessageRouter()
        broker = MessageBroker(router, dlq_max_size=3)
        for i in range(5):
            broker.enqueue(Message(sender="a", recipient="b", payload=i, ttl=-1))
        assert len(broker.dead_letters) == 3
