"""gRPC protocol client with automatic metric emission.

Emits ``grpc_reqs``, ``grpc_req_duration``, ``grpc_req_failed``,
``grpc_streams_opened``, ``grpc_messages_sent``, and
``grpc_messages_received`` metrics.

Requires the ``grpcio`` optional dependency.

>>> import rampa.protocols.grpc
"""

from __future__ import annotations

import queue
import time
import typing as t

from rampa._types import Sample, make_sample


class GrpcResponse:
    """Response from a gRPC unary call.

    >>> r = GrpcResponse(data=b"ok", status_code=0, metadata={})
    >>> r.status_code
    0
    """

    def __init__(
        self,
        data: bytes,
        status_code: int,
        metadata: dict[str, str],
    ) -> None:
        self.data = data
        self.status_code = status_code
        self.metadata = metadata

    @property
    def ok(self) -> bool:
        """Return True if the status code is OK (0).

        >>> GrpcResponse(b"", 0, {}).ok
        True
        >>> GrpcResponse(b"", 2, {}).ok
        False
        """
        return self.status_code == 0


class GrpcClient:
    """gRPC client with automatic metric emission.

    Uses ``grpc.aio`` for async RPC calls. Lazily initialized via
    ``worker.grpc``.

    >>> import rampa.protocols.grpc
    """

    def __init__(
        self,
        sample_queue: queue.SimpleQueue[Sample | None],
        tags: dict[str, str],
    ) -> None:
        self._queue = sample_queue
        self._tags = tags
        self._channels: dict[str, t.Any] = {}

    def _get_channel(self, target: str) -> t.Any:
        """Get or create a gRPC channel for the target.

        Parameters
        ----------
        target : str
            gRPC target (e.g. ``"localhost:50051"``).
        """
        if target not in self._channels:
            import grpc

            self._channels[target] = grpc.aio.insecure_channel(target)
        return self._channels[target]

    async def unary(
        self,
        target: str,
        method: str,
        request: bytes,
        metadata: dict[str, str] | None = None,
    ) -> GrpcResponse:
        """Make a unary gRPC call.

        Parameters
        ----------
        target : str
            gRPC target (e.g. ``"localhost:50051"``).
        method : str
            Full method path (e.g. ``"/pkg.Service/Method"``).
        request : bytes
            Serialized protobuf request.
        metadata : dict[str, str] | None
            Optional gRPC metadata.

        Returns
        -------
        GrpcResponse
            The response.
        """
        import grpc

        channel = self._get_channel(target)
        call_tags = {**self._tags, "method": method}

        start = time.monotonic()
        status_code = 0
        try:
            response = await channel.unary_unary(
                method,
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, metadata=list((metadata or {}).items()))

            self._queue.put(make_sample("grpc_reqs", 1.0, call_tags))
            return GrpcResponse(data=response, status_code=0, metadata={})

        except grpc.aio.AioRpcError as exc:
            status_code = exc.code().value[0]
            self._queue.put(make_sample("grpc_req_failed", 1.0, call_tags))
            self._queue.put(make_sample("grpc_reqs", 1.0, call_tags))
            return GrpcResponse(
                data=b"",
                status_code=status_code,
                metadata={},
            )
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._queue.put(make_sample("grpc_req_duration", elapsed_ms, call_tags))

    async def server_stream(
        self,
        target: str,
        method: str,
        request: bytes,
        metadata: dict[str, str] | None = None,
    ) -> t.AsyncIterator[bytes]:
        """Make a server-streaming gRPC call.

        Parameters
        ----------
        target : str
            gRPC target.
        method : str
            Full method path.
        request : bytes
            Serialized protobuf request.
        metadata : dict[str, str] | None
            Optional gRPC metadata.

        Yields
        ------
        bytes
            Serialized protobuf response messages.
        """
        channel = self._get_channel(target)
        call_tags = {**self._tags, "method": method}

        self._queue.put(make_sample("grpc_streams_opened", 1.0, call_tags))
        start = time.monotonic()

        try:
            call = channel.unary_stream(
                method,
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, metadata=list((metadata or {}).items()))

            async for response in call:
                self._queue.put(make_sample("grpc_messages_received", 1.0, call_tags))
                yield response
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._queue.put(make_sample("grpc_req_duration", elapsed_ms, call_tags))

    async def close(self) -> None:
        """Close all channels."""
        for channel in self._channels.values():
            await channel.close()
        self._channels.clear()
