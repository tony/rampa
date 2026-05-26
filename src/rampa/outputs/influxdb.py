"""InfluxDB output — pushes samples as line protocol over HTTP.

Each sample becomes one InfluxDB line::

    metric_name,tag_key=tag_val value=42.0 1716691200000000000

>>> import rampa.outputs.influxdb
"""

from __future__ import annotations

import logging
import typing as t

from rampa._types import Sample

logger = logging.getLogger(__name__)


def _escape_tag(s: str) -> str:
    r"""Escape special characters in InfluxDB tag keys and values.

    >>> _escape_tag("hello world")
    'hello\\ world'
    >>> _escape_tag("a,b=c")
    'a\\,b\\=c'
    """
    return s.replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def _sample_to_line(sample: Sample) -> str:
    """Convert a sample to InfluxDB line protocol.

    >>> from rampa._types import Sample
    >>> s = Sample(metric="reqs", value=1.0, timestamp=1000000000, tags={})
    >>> _sample_to_line(s)
    'reqs value=1.0 1000000000'
    >>> s2 = Sample(
    ...     metric="dur", value=45.2, timestamp=2000000000,
    ...     tags={"method": "GET"},
    ... )
    >>> _sample_to_line(s2)
    'dur,method=GET value=45.2 2000000000'
    """
    parts = [sample.metric]
    if sample.tags:
        tag_str = ",".join(
            f"{_escape_tag(k)}={_escape_tag(v)}" for k, v in sorted(sample.tags.items())
        )
        parts[0] = f"{sample.metric},{tag_str}"
    return f"{parts[0]} value={sample.value} {sample.timestamp}"


class InfluxDBOutput:
    """Push samples to InfluxDB via the HTTP write API.

    Batches samples and writes them as line protocol on ``stop()``
    and periodically during ``add_samples()``.

    Parameters
    ----------
    url : str
        InfluxDB write endpoint, e.g.
        ``"http://localhost:8086/api/v2/write?org=myorg&bucket=rampa"``.
    token : str
        Authentication token. Empty string disables auth header.
    batch_size : int
        Flush after accumulating this many lines.

    >>> o = InfluxDBOutput("http://localhost:8086/api/v2/write")
    >>> o._url
    'http://localhost:8086/api/v2/write'
    """

    def __init__(
        self,
        url: str,
        token: str = "",
        batch_size: int = 5000,
    ) -> None:
        self._url = url
        self._token = token
        self._batch_size = batch_size
        self._buffer: list[str] = []
        self._session: t.Any = None

    async def start(self) -> None:
        """Open an aiohttp session for writing."""
        import aiohttp

        self._session = aiohttp.ClientSession()

    async def add_samples(self, samples: list[Sample]) -> None:
        """Buffer samples and flush when batch_size is reached.

        Parameters
        ----------
        samples : list[Sample]
            Batch of samples.
        """
        for s in samples:
            self._buffer.append(_sample_to_line(s))
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
        body = "\n".join(self._buffer)
        self._buffer.clear()
        headers: dict[str, str] = {"Content-Type": "text/plain"}
        if self._token:
            headers["Authorization"] = f"Token {self._token}"
        try:
            async with self._session.post(
                self._url,
                data=body,
                headers=headers,
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(
                        "influxdb write failed: %d %s",
                        resp.status,
                        text[:200],
                    )
        except Exception:
            logger.exception("influxdb write error")
