(protocols)=

# Protocol clients

rampa provides protocol-specific clients that auto-emit metrics.
Each client is lazily initialized via a {class}`~rampa.worker.Worker` property.

## HTTP (built-in)

```python
@rampa.scenario(vus=10, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://example.com/api")
    worker.check(resp, {"status 200": lambda r: r.status == 200})
```

Metrics: `http_reqs`, `http_req_duration`, `http_req_failed`, phase timings.

## WebSocket (built-in)

```python
@rampa.scenario(vus=50, duration="1m")
async def websocket_load(worker: rampa.Worker) -> None:
    async with worker.ws.connect("wss://echo.example.com") as session:
        await session.send('{"type": "ping"}')
        response = await session.receive()
        worker.check(response, {"got pong": lambda r: "pong" in r})
```

Metrics: `ws_sessions`, `ws_connecting`, `ws_session_duration`,
`ws_messages_sent`, `ws_messages_received`, `ws_errors`.

## gRPC (optional)

Install: `pip install rampa[grpc]`

```python
@rampa.scenario(vus=20, duration="30s")
async def grpc_load(worker: rampa.Worker) -> None:
    resp = await worker.grpc.unary(
        "localhost:50051",
        "/myservice.MyService/GetUser",
        request=b"\x08\x01",  # serialized protobuf
    )
    worker.check(resp, {"ok": lambda r: r.ok})
```

Metrics: `grpc_reqs`, `grpc_req_duration`, `grpc_req_failed`,
`grpc_streams_opened`, `grpc_messages_received`.

Supports `unary()` and `server_stream()` call patterns.

## Custom protocols

For protocols without a built-in client, use raw async code with
custom metric emission:

```python
@rampa.scenario(vus=10, duration="30s")
async def tcp_load(worker: rampa.Worker) -> None:
    import asyncio, time

    start = time.monotonic()
    reader, writer = await asyncio.open_connection("localhost", 9999)
    worker.trend("tcp_connect", (time.monotonic() - start) * 1000)

    writer.write(b"PING\n")
    await writer.drain()
    data = await reader.readline()

    worker.trend("tcp_roundtrip", (time.monotonic() - start) * 1000)
    worker.counter("tcp_messages")
    worker.check(data, {"got pong": lambda d: d.strip() == b"PONG"})

    writer.close()
    await writer.wait_closed()
```
