"""Protocol definitions for message framing and handshakes."""

from __future__ import annotations

import json
import struct
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .message import Message, MessageType


class FrameType(int, Enum):
    """Wire frame types."""

    DATA = 0x01
    ACK = 0x02
    NACK = 0x03
    HANDSHAKE_INIT = 0x10
    HANDSHAKE_ACCEPT = 0x11
    HANDSHAKE_REJECT = 0x12
    HEARTBEAT = 0x20
    DISCONNECT = 0x30


class HandshakeKind(str, Enum):
    """Handshake negotiation styles."""

    BASIC = "basic"
    AUTHENTICATED = "authenticated"
    ENCRYPTED = "encrypted"


@dataclass
class Frame:
    """A single frame on the wire.

    Layout (conceptual):
        [type:1B][length:4B][payload:NB]

    Attributes:
        type: Frame type discriminator.
        payload: Raw bytes carrying the frame data.
        frame_id: Unique frame identifier.
        timestamp: Creation time.
    """

    type: FrameType
    payload: bytes = b""
    frame_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def encode(self) -> bytes:
        """Encode the frame into bytes: type(1) + length(4) + payload."""
        length = len(self.payload)
        return struct.pack("!BI", self.type.value, length) + self.payload

    @classmethod
    def decode(cls, data: bytes) -> Frame:
        """Decode bytes back into a Frame."""
        if len(data) < 5:
            raise ValueError("Frame data too short")
        ftype, length = struct.unpack("!BI", data[:5])
        payload = data[5 : 5 + length]
        return cls(type=FrameType(ftype), payload=payload)


@dataclass
class HandshakeInit:
    """Initial handshake message exchanged between agents."""

    agent_id: str
    protocol_version: str = "1.0"
    kind: HandshakeKind = HandshakeKind.BASIC
    capabilities: list[str] = field(default_factory=list)
    challenge: str | None = None


@dataclass
class HandshakeAccept:
    """Acceptance of a handshake."""

    agent_id: str
    accepted: bool = True
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    shared_capabilities: list[str] = field(default_factory=list)


class Protocol:
    """Defines message serialization, framing, and handshake helpers.

    This class centralises the on-the-wire format so that all agents
    in a Cocapn fleet can interoperate.
    """

    PROTOCOL_VERSION = "1.0"

    # ------------------------------------------------------------------
    # Message <-> Frame helpers
    # ------------------------------------------------------------------

    @staticmethod
    def message_to_frame(message: Message) -> Frame:
        """Serialize a Message into a DATA Frame."""
        json_bytes = json.dumps(message.to_dict()).encode("utf-8")
        return Frame(type=FrameType.DATA, payload=json_bytes)

    @staticmethod
    def frame_to_message(frame: Frame) -> Message:
        """Deserialize a DATA Frame back into a Message."""
        if frame.type != FrameType.DATA:
            raise ValueError(f"Expected DATA frame, got {frame.type.name}")
        data = json.loads(frame.payload.decode("utf-8"))
        return Message.from_dict(data)

    # ------------------------------------------------------------------
    # Handshake helpers
    # ------------------------------------------------------------------

    @staticmethod
    def init_handshake(
        agent_id: str,
        *,
        kind: HandshakeKind = HandshakeKind.BASIC,
        capabilities: list[str] | None = None,
    ) -> tuple[HandshakeInit, Frame]:
        """Create a handshake init and its corresponding frame."""
        init = HandshakeInit(
            agent_id=agent_id,
            protocol_version=Protocol.PROTOCOL_VERSION,
            kind=kind,
            capabilities=capabilities or [],
        )
        payload = json.dumps(
            {
                "agent_id": init.agent_id,
                "protocol_version": init.protocol_version,
                "kind": init.kind.value,
                "capabilities": init.capabilities,
            }
        ).encode("utf-8")
        frame = Frame(type=FrameType.HANDSHAKE_INIT, payload=payload)
        return init, frame

    @staticmethod
    def accept_handshake(
        init: HandshakeInit,
        *,
        our_capabilities: list[str] | None = None,
    ) -> tuple[HandshakeAccept, Frame]:
        """Accept a handshake and return the accept frame."""
        ours = set(our_capabilities or [])
        shared = sorted(ours.intersection(init.capabilities))
        accept = HandshakeAccept(
            agent_id=init.agent_id,
            shared_capabilities=shared,
        )
        payload = json.dumps(
            {
                "agent_id": accept.agent_id,
                "session_id": accept.session_id,
                "shared_capabilities": accept.shared_capabilities,
            }
        ).encode("utf-8")
        frame = Frame(type=FrameType.HANDSHAKE_ACCEPT, payload=payload)
        return accept, frame

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    @staticmethod
    def heartbeat_frame() -> Frame:
        payload = json.dumps({"ts": time.time()}).encode("utf-8")
        return Frame(type=FrameType.HEARTBEAT, payload=payload)

    @staticmethod
    def disconnect_frame() -> Frame:
        return Frame(type=FrameType.DISCONNECT)
