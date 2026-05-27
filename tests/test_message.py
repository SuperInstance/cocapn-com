"""Tests for cocapn_com.message."""

import time

from cocapn_com.message import Message, MessageType, Priority


class TestMessageCreation:
    def test_basic_fields(self):
        msg = Message(sender="alice", recipient="bob", payload="hello")
        assert msg.sender == "alice"
        assert msg.recipient == "bob"
        assert msg.payload == "hello"
        assert msg.type == MessageType.TEXT
        assert msg.priority == Priority.NORMAL
        assert msg.id  # auto-generated
        assert msg.timestamp > 0

    def test_all_types(self):
        for t in MessageType:
            msg = Message(sender="a", recipient="b", payload=None, type=t)
            assert msg.type == t

    def test_all_priorities(self):
        for p in Priority:
            msg = Message(sender="a", recipient="b", payload=None, priority=p)
            assert msg.priority == p

    def test_headers(self):
        msg = Message(
            sender="a", recipient="b", payload="x", headers={"trace": "123"}
        )
        assert msg.headers["trace"] == "123"

    def test_correlation_id(self):
        original = Message(sender="a", recipient="b", payload="q")
        reply = original.reply("a")
        assert reply.correlation_id == original.id
        assert reply.recipient == "a"
        assert reply.type == MessageType.RESPONSE


class TestMessageExpiry:
    def test_no_ttl_never_expires(self):
        msg = Message(sender="a", recipient="b", payload="x")
        assert not msg.is_expired()

    def test_ttl_expiry(self):
        msg = Message(
            sender="a",
            recipient="b",
            payload="x",
            ttl=-1,  # already expired
        )
        assert msg.is_expired()

    def test_ttl_not_yet_expired(self):
        msg = Message(
            sender="a",
            recipient="b",
            payload="x",
            ttl=9999,
        )
        assert not msg.is_expired()


class TestMessageSerialization:
    def test_round_trip(self):
        msg = Message(
            sender="alice",
            recipient="bob",
            payload={"key": "value"},
            type=MessageType.COMMAND,
            priority=Priority.HIGH,
            headers={"x-foo": "bar"},
            correlation_id="corr123",
            ttl=60.0,
        )
        d = msg.to_dict()
        restored = Message.from_dict(d)
        assert restored.sender == msg.sender
        assert restored.recipient == msg.recipient
        assert restored.payload == msg.payload
        assert restored.type == MessageType.COMMAND
        assert restored.priority == Priority.HIGH
        assert restored.headers == msg.headers
        assert restored.correlation_id == msg.correlation_id
        assert restored.ttl == msg.ttl

    def test_from_dict_string_enums(self):
        d = {
            "sender": "a",
            "recipient": "b",
            "payload": "hi",
            "type": "event",
            "priority": 3,
        }
        msg = Message.from_dict(d)
        assert msg.type == MessageType.EVENT
        assert msg.priority == Priority.URGENT


class TestMessageReply:
    def test_reply_preserves_sender(self):
        original = Message(sender="alice", recipient="bob", payload="ping")
        reply = original.reply("pong")
        assert reply.sender == "bob"
        assert reply.recipient == "alice"
        assert reply.payload == "pong"
        assert reply.type == MessageType.RESPONSE

    def test_reply_custom_type(self):
        original = Message(sender="a", recipient="b", payload="q")
        reply = original.reply("a", type=MessageType.EVENT)
        assert reply.type == MessageType.EVENT
