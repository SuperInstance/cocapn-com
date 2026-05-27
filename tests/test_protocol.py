"""Tests for cocapn_com.protocol."""

import json

from cocapn_com.message import Message, MessageType, Priority
from cocapn_com.protocol import (
    Frame,
    FrameType,
    HandshakeAccept,
    HandshakeKind,
    Protocol,
)


class TestFrame:
    def test_encode_decode_roundtrip(self):
        f = Frame(type=FrameType.DATA, payload=b"hello world")
        encoded = f.encode()
        decoded = Frame.decode(encoded)
        assert decoded.type == FrameType.DATA
        assert decoded.payload == b"hello world"

    def test_empty_payload(self):
        f = Frame(type=FrameType.HEARTBEAT)
        encoded = f.encode()
        decoded = Frame.decode(encoded)
        assert decoded.type == FrameType.HEARTBEAT
        assert decoded.payload == b""

    def test_decode_too_short(self):
        import pytest
        with pytest.raises(ValueError, match="too short"):
            Frame.decode(b"\x01\x00")

    def test_disconnect_frame(self):
        f = Frame(type=FrameType.DISCONNECT)
        encoded = f.encode()
        assert len(encoded) == 5  # type(1) + length(4)


class TestProtocolMessageFrame:
    def test_message_roundtrip(self):
        msg = Message(
            sender="alice",
            recipient="bob",
            payload={"action": "compute"},
            type=MessageType.COMMAND,
            priority=Priority.HIGH,
        )
        frame = Protocol.message_to_frame(msg)
        assert frame.type == FrameType.DATA

        restored = Protocol.frame_to_message(frame)
        assert restored.sender == msg.sender
        assert restored.recipient == msg.recipient
        assert restored.payload == msg.payload
        assert restored.type == MessageType.COMMAND
        assert restored.priority == Priority.HIGH

    def test_frame_to_message_wrong_type(self):
        import pytest
        f = Frame(type=FrameType.ACK)
        with pytest.raises(ValueError, match="Expected DATA frame"):
            Protocol.frame_to_message(f)


class TestHandshake:
    def test_init_handshake(self):
        init, frame = Protocol.init_handshake(
            "agent-1",
            kind=HandshakeKind.AUTHENTICATED,
            capabilities=["pub_sub", "rpc"],
        )
        assert init.agent_id == "agent-1"
        assert init.kind == HandshakeKind.AUTHENTICATED
        assert frame.type == FrameType.HANDSHAKE_INIT
        data = json.loads(frame.payload)
        assert data["agent_id"] == "agent-1"

    def test_accept_handshake(self):
        init = Protocol.init_handshake("agent-1", capabilities=["a", "b", "c"])[0]
        accept, frame = Protocol.accept_handshake(init, our_capabilities=["b", "d"])
        assert accept.shared_capabilities == ["b"]
        assert frame.type == FrameType.HANDSHAKE_ACCEPT

    def test_heartbeat_frame(self):
        f = Protocol.heartbeat_frame()
        assert f.type == FrameType.HEARTBEAT
        data = json.loads(f.payload)
        assert "ts" in data

    def test_disconnect_frame(self):
        f = Protocol.disconnect_frame()
        assert f.type == FrameType.DISCONNECT
        assert f.payload == b""
