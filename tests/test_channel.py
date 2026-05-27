"""Tests for cocapn_com.channel."""

from cocapn_com.channel import Channel, ChannelMode
from cocapn_com.message import Message, MessageType


class TestChannelSubscribe:
    def test_subscribe_and_count(self):
        ch = Channel("test", ChannelMode.PUB_SUB)
        ch.subscribe("agent1", lambda m: None)
        assert ch.subscriber_count == 1

    def test_unsubscribe(self):
        ch = Channel("test")
        ch.subscribe("agent1", lambda m: None)
        ch.unsubscribe("agent1")
        assert ch.subscriber_count == 0

    def test_multiple_subscribers(self):
        ch = Channel("test")
        ch.subscribe("a", lambda m: None)
        ch.subscribe("b", lambda m: None)
        ch.subscribe("c", lambda m: None)
        assert ch.subscriber_count == 3


class TestChannelDeliverPubSub:
    def test_all_subscribers_receive(self):
        received: list[str] = []
        ch = Channel("test", ChannelMode.PUB_SUB)
        ch.subscribe("a", lambda m: received.append("a"))
        ch.subscribe("b", lambda m: received.append("b"))
        msg = Message(sender="x", recipient=None, payload="hi")
        delivered = ch.deliver(msg)
        assert set(delivered) == {"a", "b"}
        assert set(received) == {"a", "b"}


class TestChannelDeliverPointToPoint:
    def test_only_recipient_receives(self):
        received: list[str] = []
        ch = Channel("test", ChannelMode.POINT_TO_POINT)
        ch.subscribe("a", lambda m: received.append("a"))
        ch.subscribe("b", lambda m: received.append("b"))
        msg = Message(sender="x", recipient="a", payload="hi")
        delivered = ch.deliver(msg)
        assert delivered == ["a"]
        assert received == ["a"]

    def test_no_recipient_delivers_nothing(self):
        ch = Channel("test", ChannelMode.POINT_TO_POINT)
        ch.subscribe("a", lambda m: None)
        msg = Message(sender="x", recipient=None, payload="hi")
        delivered = ch.deliver(msg)
        assert delivered == []


class TestChannelDeliverBroadcast:
    def test_broadcast_ignores_recipient(self):
        received: list[str] = []
        ch = Channel("test", ChannelMode.BROADCAST)
        ch.subscribe("a", lambda m: received.append("a"))
        ch.subscribe("b", lambda m: received.append("b"))
        msg = Message(sender="x", recipient="a", payload="hi")
        delivered = ch.deliver(msg)
        assert set(delivered) == {"a", "b"}
        assert set(received) == {"a", "b"}


class TestChannelHandlerError:
    def test_bad_handler_does_not_crash(self):
        received: list[str] = []
        ch = Channel("test", ChannelMode.PUB_SUB)

        def bad_handler(m):
            raise RuntimeError("boom")

        ch.subscribe("a", bad_handler)
        ch.subscribe("b", lambda m: received.append("b"))
        msg = Message(sender="x", recipient=None, payload="hi")
        delivered = ch.deliver(msg)
        # "a" is still in delivered list even though handler threw
        assert "b" in delivered
        assert received == ["b"]
