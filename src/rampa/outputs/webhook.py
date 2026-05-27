"""Webhook output — POST metric batches to an HTTP endpoint.

>>> import rampa.outputs.webhook
"""

from __future__ import annotations

import json
import logging
import typing as t

from rampa._types import Sample

logger = logging.getLogger(__name__)


class WebhookOutput:
    """POST sample batches as JSON to an HTTP endpoint.

    Parameters
    ----------
    url : str
        Webhook URL.
    headers : dict[str, str] | None
        Extra HTTP headers (e.g. auth tokens).
    batch_size : int
        Flush after accumulating this many samples.

    >>> o = WebhookOutput("https://example.com/hook")
    >>> o._url
    'https://example.com/hook'
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        batch_size: int = 1000,
    ) -> None:
        self._url = url
        self._extra_headers = headers or {}
        self._batch_size = batch_size
        self._buffer: list[dict[str, t.Any]] = []
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
        for s in samples:
            self._buffer.append(
                {
                    "metric": s.metric,
                    "value": s.value,
                    "timestamp": s.timestamp,
                    "tags": s.tags,
                },
            )
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
        payload = json.dumps({"samples": self._buffer})
        self._buffer.clear()
        headers = {
            "Content-Type": "application/json",
            **self._extra_headers,
        }
        try:
            async with self._session.post(
                self._url,
                data=payload,
                headers=headers,
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(
                        "webhook POST failed: %d %s",
                        resp.status,
                        text[:200],
                    )
        except Exception:
            logger.exception("webhook POST error")
