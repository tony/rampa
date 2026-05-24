"""HTTP client with automatic metric emission for rampa.

Wraps ``aiohttp.ClientSession`` and emits timing metrics for every request:
``http_reqs``, ``http_req_duration``, ``http_req_failed``, and data transfer
counters.

>>> import rampa.http
"""

from __future__ import annotations

import queue
import time
import typing as t
from dataclasses import dataclass

import aiohttp

from rampa._types import Sample, make_sample


@dataclass(frozen=True)
class Response:
    """Wrapper around an HTTP response with metric-relevant fields.

    >>> r = Response(status=200, headers={}, body=b"ok", url="http://x")
    >>> r.status
    200
    """

    status: int
    headers: dict[str, str]
    body: bytes
    url: str

    def json(self) -> t.Any:
        """Parse the response body as JSON.

        Returns
        -------
        Any
            Parsed JSON data.

        >>> import json
        >>> r = Response(
        ...     status=200, headers={}, body=b'{"a": 1}', url="",
        ... )
        >>> r.json()
        {'a': 1}
        """
        import json

        return json.loads(self.body)

    def text(self) -> str:
        """Decode the response body as UTF-8 text.

        Returns
        -------
        str
            Decoded body.

        >>> r = Response(status=200, headers={}, body=b"hello", url="")
        >>> r.text()
        'hello'
        """
        return self.body.decode("utf-8", errors="replace")


def _estimate_request_size(kwargs: dict[str, t.Any]) -> int:
    """Estimate the size of an outgoing request body in bytes.

    Parameters
    ----------
    kwargs : dict[str, Any]
        Request keyword arguments.

    Returns
    -------
    int
        Estimated body size in bytes.

    >>> _estimate_request_size({"data": "hello"})
    5
    >>> _estimate_request_size({"data": b"bytes"})
    5
    >>> _estimate_request_size({})
    0
    """
    data = kwargs.get("data")
    if data is not None:
        if isinstance(data, (str, bytes)):
            return len(data)
        return 0
    json_data = kwargs.get("json")
    if json_data is not None:
        import json

        return len(json.dumps(json_data).encode())
    return 0


class HttpClient:
    """HTTP client that auto-emits metrics for every request.

    Parameters
    ----------
    sample_queue : queue.SimpleQueue[Sample | None]
        Queue for emitting metric samples.
    tags : dict[str, str]
        Base tags added to every sample (e.g. scenario name).

    >>> import queue as q
    >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
    >>> client = HttpClient(sq, {"scenario": "test"})
    >>> client._tags["scenario"]
    'test'
    """

    def __init__(
        self,
        sample_queue: queue.SimpleQueue[Sample | None],
        tags: dict[str, str],
    ) -> None:
        self._queue = sample_queue
        self._tags = tags
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def __aenter__(self) -> HttpClient:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager and close the session."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _emit(self, metric: str, value: float, extra_tags: dict[str, str] | None = None) -> None:
        tags = dict(self._tags)
        if extra_tags:
            tags.update(extra_tags)
        self._queue.put(make_sample(metric, value, tags))

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: t.Any,
    ) -> Response:
        """Send an HTTP request and emit timing metrics.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, etc.).
        url : str
            Request URL.
        **kwargs : Any
            Additional arguments passed to ``aiohttp.ClientSession.request``.

        Returns
        -------
        Response
            The response wrapper.
        """
        session = await self._ensure_session()
        request_tags = {"method": method, "url": url}

        sent_bytes = _estimate_request_size(kwargs)

        start_ns = time.monotonic_ns()
        try:
            async with session.request(method, url, **kwargs) as resp:
                body = await resp.read()
                elapsed_ns = time.monotonic_ns() - start_ns
                elapsed_ms = elapsed_ns / 1_000_000

                request_tags["status"] = str(resp.status)

                self._emit("http_reqs", 1.0, request_tags)
                self._emit("http_req_duration", elapsed_ms, request_tags)

                failed = 0.0 if 200 <= resp.status < 400 else 1.0
                self._emit("http_req_failed", failed, request_tags)

                self._emit("data_sent", float(sent_bytes), request_tags)
                content_length = len(body)
                self._emit("data_received", float(content_length), request_tags)

                headers = dict(resp.headers.items())

                return Response(
                    status=resp.status,
                    headers=headers,
                    body=body,
                    url=str(resp.url),
                )
        except Exception as exc:
            elapsed_ns = time.monotonic_ns() - start_ns
            elapsed_ms = elapsed_ns / 1_000_000

            request_tags["error"] = type(exc).__name__

            self._emit("http_reqs", 1.0, request_tags)
            self._emit("http_req_duration", elapsed_ms, request_tags)
            self._emit("http_req_failed", 1.0, request_tags)
            self._emit("data_sent", float(sent_bytes), request_tags)
            raise

    async def get(self, url: str, **kwargs: t.Any) -> Response:
        """Send a GET request.

        Parameters
        ----------
        url : str
            Request URL.
        **kwargs : Any
            Additional arguments.

        Returns
        -------
        Response
            The response wrapper.
        """
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: t.Any) -> Response:
        """Send a POST request.

        Parameters
        ----------
        url : str
            Request URL.
        **kwargs : Any
            Additional arguments.

        Returns
        -------
        Response
            The response wrapper.
        """
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: t.Any) -> Response:
        """Send a PUT request.

        Parameters
        ----------
        url : str
            Request URL.
        **kwargs : Any
            Additional arguments.

        Returns
        -------
        Response
            The response wrapper.
        """
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: t.Any) -> Response:
        """Send a DELETE request.

        Parameters
        ----------
        url : str
            Request URL.
        **kwargs : Any
            Additional arguments.

        Returns
        -------
        Response
            The response wrapper.
        """
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: t.Any) -> Response:
        """Send a PATCH request.

        Parameters
        ----------
        url : str
            Request URL.
        **kwargs : Any
            Additional arguments.

        Returns
        -------
        Response
            The response wrapper.
        """
        return await self.request("PATCH", url, **kwargs)
