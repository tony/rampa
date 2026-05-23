"""Tests for rampa HTTP client with a local aiohttp test server."""

from __future__ import annotations

import asyncio
import queue

from aiohttp import web

from rampa._types import Sample
from rampa.http import HttpClient


def _drain(sq: queue.SimpleQueue[Sample | None]) -> list[Sample]:
    """Drain all samples from a queue."""
    samples: list[Sample] = []
    while True:
        try:
            s = sq.get_nowait()
        except Exception:
            break
        if s is not None:
            samples.append(s)
    return samples


async def _ok_handler(request: web.Request) -> web.Response:
    """Return 200 OK with JSON body."""
    return web.json_response({"status": "ok"})


async def _error_handler(request: web.Request) -> web.Response:
    """Return 500 Internal Server Error."""
    return web.Response(status=500, text="error")


def test_http_get_emits_metrics() -> None:
    """HttpClient.get emits http_reqs, http_req_duration, http_req_failed."""

    async def _run() -> list[Sample]:
        app = web.Application()
        app.router.add_get("/ok", _ok_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
        port = addr[1]

        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        client = HttpClient(sq, {"scenario": "test"})
        try:
            resp = await client.get(f"http://127.0.0.1:{port}/ok")
            assert resp.status == 200
            assert resp.json() == {"status": "ok"}
        finally:
            await client.close()
            await runner.cleanup()

        return _drain(sq)

    samples = asyncio.run(_run())
    metrics = {s.metric for s in samples}
    assert "http_reqs" in metrics
    assert "http_req_duration" in metrics
    assert "http_req_failed" in metrics
    assert "data_received" in metrics

    failed_sample = next(s for s in samples if s.metric == "http_req_failed")
    assert failed_sample.value == 0.0

    duration_sample = next(s for s in samples if s.metric == "http_req_duration")
    assert duration_sample.value > 0


def test_http_get_error_marks_failed() -> None:
    """HttpClient marks 5xx responses as failed."""

    async def _run() -> list[Sample]:
        app = web.Application()
        app.router.add_get("/err", _error_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
        port = addr[1]

        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        client = HttpClient(sq, {"scenario": "test"})
        try:
            resp = await client.get(f"http://127.0.0.1:{port}/err")
            assert resp.status == 500
        finally:
            await client.close()
            await runner.cleanup()

        return _drain(sq)

    samples = asyncio.run(_run())
    failed_sample = next(s for s in samples if s.metric == "http_req_failed")
    assert failed_sample.value == 1.0


def test_http_post() -> None:
    """HttpClient.post sends a POST request."""

    async def _run() -> list[Sample]:
        async def _post_handler(request: web.Request) -> web.Response:
            body = await request.text()
            return web.Response(text=f"got: {body}")

        app = web.Application()
        app.router.add_post("/post", _post_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
        port = addr[1]

        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        client = HttpClient(sq, {"scenario": "test"})
        try:
            resp = await client.post(
                f"http://127.0.0.1:{port}/post",
                data="hello",
            )
            assert resp.status == 200
            assert "got: hello" in resp.text()
        finally:
            await client.close()
            await runner.cleanup()

        return _drain(sq)

    samples = asyncio.run(_run())
    reqs = [s for s in samples if s.metric == "http_reqs"]
    assert len(reqs) == 1
    assert reqs[0].tags["method"] == "POST"


def test_http_response_text_and_json() -> None:
    """Response.text() and Response.json() work correctly."""

    async def _run() -> None:
        app = web.Application()
        app.router.add_get("/json", _ok_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
        port = addr[1]

        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        client = HttpClient(sq, {})
        try:
            resp = await client.get(f"http://127.0.0.1:{port}/json")
            assert resp.json() == {"status": "ok"}
            assert isinstance(resp.text(), str)
        finally:
            await client.close()
            await runner.cleanup()

    asyncio.run(_run())


def test_http_tags_include_method_and_status() -> None:
    """HTTP samples include method and status tags."""

    async def _run() -> list[Sample]:
        app = web.Application()
        app.router.add_get("/ok", _ok_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
        port = addr[1]

        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        client = HttpClient(sq, {"scenario": "load"})
        try:
            await client.get(f"http://127.0.0.1:{port}/ok")
        finally:
            await client.close()
            await runner.cleanup()

        return _drain(sq)

    samples = asyncio.run(_run())
    reqs = next(s for s in samples if s.metric == "http_reqs")
    assert reqs.tags["method"] == "GET"
    assert reqs.tags["status"] == "200"
    assert reqs.tags["scenario"] == "load"
