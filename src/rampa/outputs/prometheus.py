"""Prometheus remote write output.

Pushes metrics to Prometheus via the remote write HTTP API using
protobuf v1 wire format with snappy compression.

Falls back to gzip if python-snappy is not installed.

>>> import rampa.outputs.prometheus
"""

from __future__ import annotations

import gzip
import logging
import struct
import time
import typing as t

from rampa._types import Sample

logger = logging.getLogger(__name__)


def _encode_varint(value: int) -> bytes:
    r"""Encode an unsigned integer as a protobuf varint.

    >>> _encode_varint(0)
    b'\x00'
    >>> _encode_varint(150)
    b'\x96\x01'
    """
    parts: list[int] = []
    while value > 0x7F:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.append(value & 0x7F)
    return bytes(parts)


def _encode_signed_varint(value: int) -> bytes:
    r"""Encode a signed integer as a protobuf varint (zigzag).

    >>> _encode_signed_varint(0)
    b'\x00'
    """
    if value >= 0:
        return _encode_varint(value)
    return _encode_varint(((-value) << 1) - 1)


def _encode_field(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_string(field_number: int, value: str) -> bytes:
    r"""Encode a protobuf string field (wire type 2).

    >>> _encode_string(1, "a")
    b'\n\x01a'
    """
    data = value.encode("utf-8")
    return _encode_field(field_number, 2) + _encode_varint(len(data)) + data


def _encode_double(field_number: int, value: float) -> bytes:
    """Encode a protobuf double field (wire type 1).

    >>> len(_encode_double(1, 3.14))
    9
    """
    return _encode_field(field_number, 1) + struct.pack("<d", value)


def _encode_int64(field_number: int, value: int) -> bytes:
    return _encode_field(field_number, 0) + _encode_varint(value)


def _encode_submessage(field_number: int, data: bytes) -> bytes:
    return _encode_field(field_number, 2) + _encode_varint(len(data)) + data


def _encode_label(name: str, value: str) -> bytes:
    return _encode_string(1, name) + _encode_string(2, value)


def _encode_sample(value: float, timestamp_ms: int) -> bytes:
    return _encode_double(1, value) + _encode_int64(2, timestamp_ms)


def _encode_timeseries(
    labels: dict[str, str],
    value: float,
    timestamp_ms: int,
) -> bytes:
    """Encode a single TimeSeries protobuf message.

    >>> ts = _encode_timeseries({"__name__": "test"}, 1.0, 1000)
    >>> len(ts) > 0
    True
    """
    parts = bytearray()
    for k, v in sorted(labels.items()):
        label_data = _encode_label(k, v)
        parts.extend(_encode_submessage(1, label_data))
    sample_data = _encode_sample(value, timestamp_ms)
    parts.extend(_encode_submessage(2, sample_data))
    return bytes(parts)


def _encode_write_request(timeseries_list: list[bytes]) -> bytes:
    parts = bytearray()
    for ts in timeseries_list:
        parts.extend(_encode_submessage(1, ts))
    return bytes(parts)


def _compress(data: bytes) -> tuple[bytes, str]:
    """Compress with snappy if available, gzip otherwise.

    >>> compressed, encoding = _compress(b"hello")
    >>> encoding in ("snappy", "gzip")
    True
    """
    try:
        import snappy  # ty: ignore[unresolved-import]

        return snappy.compress(data), "snappy"
    except ImportError:
        return gzip.compress(data), "gzip"


def _samples_to_write_request(samples: list[Sample]) -> bytes:
    """Convert rampa samples to a Prometheus WriteRequest protobuf.

    Parameters
    ----------
    samples : list[Sample]
        Batch of metric samples.

    Returns
    -------
    bytes
        Serialized WriteRequest protobuf.
    """
    timestamp_ms = int(time.time() * 1000)
    timeseries: list[bytes] = []
    for s in samples:
        labels = {"__name__": s.metric, **s.tags}
        ts = _encode_timeseries(labels, s.value, timestamp_ms)
        timeseries.append(ts)
    return _encode_write_request(timeseries)


class PrometheusOutput:
    """Push metrics to Prometheus via the remote write API.

    Uses hand-crafted protobuf v1 encoding with snappy compression
    (falls back to gzip if python-snappy is not installed).

    Parameters
    ----------
    url : str
        Remote write endpoint (e.g.
        ``"http://localhost:9090/api/v1/write"``).
    headers : dict[str, str] | None
        Extra HTTP headers (e.g. auth).
    batch_size : int
        Flush after accumulating this many samples.

    >>> o = PrometheusOutput("http://localhost:9090/api/v1/write")
    >>> o._url
    'http://localhost:9090/api/v1/write'
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        batch_size: int = 5000,
    ) -> None:
        self._url = url
        self._extra_headers = headers or {}
        self._batch_size = batch_size
        self._buffer: list[Sample] = []
        self._session: t.Any = None

    async def start(self) -> None:
        """Open an aiohttp session."""
        import aiohttp

        self._session = aiohttp.ClientSession()

    async def add_samples(self, samples: list[Sample]) -> None:
        """Buffer samples and flush when batch_size is reached.

        Parameters
        ----------
        samples : list[Sample]
            Batch of samples.
        """
        self._buffer.extend(samples)
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def stop(self, error: Exception | None = None) -> None:
        """Flush remaining samples and close the session.

        Parameters
        ----------
        error : Exception | None
            The test error, if any.
        """
        if self._buffer:
            await self._flush()
        if self._session is not None:
            await self._session.close()

    async def _flush(self) -> None:
        if not self._buffer or self._session is None:
            return
        write_req = _samples_to_write_request(self._buffer)
        self._buffer.clear()
        body, encoding = _compress(write_req)
        headers = {
            "Content-Type": "application/x-protobuf",
            "Content-Encoding": encoding,
            "X-Prometheus-Remote-Write-Version": "0.1.0",
            **self._extra_headers,
        }
        try:
            async with self._session.post(
                self._url,
                data=body,
                headers=headers,
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(
                        "prometheus write failed: %d %s",
                        resp.status,
                        text[:200],
                    )
        except Exception:
            logger.exception("prometheus write error")
