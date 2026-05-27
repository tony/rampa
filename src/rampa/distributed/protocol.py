"""Wire protocol for distributed rampa execution.

Defines the message envelope and types exchanged between coordinator
and worker over WebSocket connections using MessagePack or JSON.

>>> import rampa.distributed.protocol
"""

from __future__ import annotations

import enum
import json
import time
import typing as t
from dataclasses import dataclass, field


class WireFormat(enum.StrEnum):
    """Wire serialization format.

    >>> WireFormat.MSGPACK.value
    'msgpack'
    """

    MSGPACK = "msgpack"
    JSON = "json"


class MessageType(enum.StrEnum):
    """Protocol message types.

    >>> MessageType.REGISTER.value
    'register'
    """

    REGISTER = "register"
    ASSIGN = "assign"
    SAMPLES = "samples"
    STOP = "stop"
    HEARTBEAT_REQ = "heartbeat_req"
    HEARTBEAT_RESP = "heartbeat_resp"
    THRESHOLD_BREACH = "threshold_breach"
    ERROR = "error"
    PHASE = "phase"


@dataclass(frozen=True)
class Envelope:
    """Wire protocol envelope wrapping all messages.

    Parameters
    ----------
    msg_type : MessageType
        The message type.
    worker_id : str
        Globally unique worker identifier.
    seq : int
        Monotonic sequence number per connection.
    payload : dict[str, Any]
        Message-specific payload.
    timestamp_ns : int
        Sender's monotonic nanosecond timestamp.

    >>> e = Envelope(
    ...     msg_type=MessageType.REGISTER,
    ...     worker_id="w-0",
    ...     seq=0,
    ...     payload={"version": "0.0.1"},
    ... )
    >>> e.msg_type
    <MessageType.REGISTER: 'register'>
    """

    msg_type: MessageType
    worker_id: str
    seq: int
    payload: dict[str, t.Any] = field(default_factory=dict)
    timestamp_ns: int = field(default_factory=time.monotonic_ns)


def encode(envelope: Envelope, fmt: WireFormat = WireFormat.JSON) -> bytes:
    """Serialize an envelope to bytes.

    Parameters
    ----------
    envelope : Envelope
        The message to serialize.
    fmt : WireFormat
        Wire format to use.

    Returns
    -------
    bytes
        Serialized message.

    >>> e = Envelope(
    ...     msg_type=MessageType.REGISTER,
    ...     worker_id="w-0",
    ...     seq=0,
    ...     payload={},
    ... )
    >>> data = encode(e)
    >>> b"register" in data
    True
    """
    d = {
        "msg_type": envelope.msg_type.value,
        "worker_id": envelope.worker_id,
        "seq": envelope.seq,
        "payload": envelope.payload,
        "timestamp_ns": envelope.timestamp_ns,
    }
    if fmt == WireFormat.MSGPACK:
        try:
            import msgpack  # ty: ignore[unresolved-import]

            return msgpack.packb(d)
        except ImportError:
            pass
    return json.dumps(d).encode()


def decode(data: bytes, fmt: WireFormat = WireFormat.JSON) -> Envelope:
    """Deserialize bytes into an Envelope.

    Parameters
    ----------
    data : bytes
        Raw message bytes.
    fmt : WireFormat
        Expected wire format.

    Returns
    -------
    Envelope
        Parsed message.

    >>> raw = encode(Envelope(
    ...     msg_type=MessageType.SAMPLES,
    ...     worker_id="w-1",
    ...     seq=5,
    ...     payload={"count": 10},
    ... ))
    >>> env = decode(raw)
    >>> env.msg_type
    <MessageType.SAMPLES: 'samples'>
    >>> env.payload["count"]
    10
    """
    if fmt == WireFormat.MSGPACK:
        try:
            import msgpack  # ty: ignore[unresolved-import]

            d = msgpack.unpackb(data, raw=False)
        except ImportError:
            d = json.loads(data)
    else:
        d = json.loads(data)

    return Envelope(
        msg_type=MessageType(d["msg_type"]),
        worker_id=d["worker_id"],
        seq=d["seq"],
        payload=d.get("payload", {}),
        timestamp_ns=d.get("timestamp_ns", 0),
    )
