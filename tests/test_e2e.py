"""End-to-end integration test for rampa.

Validates the full lifecycle: script loading, constant-vus execution with a
local HTTP server, metric emission, threshold evaluation, and exit codes.
"""

from __future__ import annotations

import asyncio
import json
import textwrap
import typing as t

from aiohttp import web

from rampa.events import RunStatus
from rampa.loader import load_test
from rampa.runner import run_test


async def _start_test_server() -> tuple[web.AppRunner, int]:
    """Start a local aiohttp server that returns 200 OK."""

    async def _handler(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_get("/api/test", _handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
    return runner, addr[1]


def test_e2e_passing_test(tmp_path: t.Any) -> None:
    """Full E2E: scenario passes all thresholds, exit code 0."""
    script = tmp_path / "test_pass.py"
    script.write_text(
        textwrap.dedent("""\
        from __future__ import annotations

        import rampa

        @rampa.scenario(executor="constant-vus", vus=2, duration="300ms")
        async def default(worker: rampa.Worker) -> None:
            resp = await worker.http.get("http://127.0.0.1:{port}/api/test")
            worker.check(resp, {
                "status is 200": lambda r: r.status == 200,
            })
    """)
    )

    async def _run() -> tuple[RunStatus, dict[str, t.Any]]:
        server_runner, port = await _start_test_server()
        try:
            final_script = tmp_path / "test_final.py"
            final_script.write_text(
                script.read_text().replace("{port}", str(port)),
            )
            plan = load_test(str(final_script))
            json_path = str(tmp_path / "result.json")
            result = await run_test(plan, json_output_path=json_path, quiet=True)
            import pathlib

            with pathlib.Path(json_path).open() as f:
                data = json.load(f)
            return result.status, data
        finally:
            await server_runner.cleanup()

    status, data = asyncio.run(_run())
    assert status == RunStatus.PASSED
    assert "summary" in data
    assert "samples" in data
    assert len(data["samples"]) > 0


def test_e2e_failing_threshold(tmp_path: t.Any) -> None:
    """Full E2E: threshold breach returns exit code 1."""
    script = tmp_path / "test_fail.py"
    script.write_text(
        textwrap.dedent("""\
        from __future__ import annotations

        import rampa
        from rampa import Config

        config = Config(
            thresholds={
                "http_req_duration": ["avg<0.001"],
            },
        )

        @rampa.scenario(executor="constant-vus", vus=1, duration="200ms")
        async def default(worker: rampa.Worker) -> None:
            await worker.http.get("http://127.0.0.1:{port}/api/test")
    """)
    )

    async def _run() -> RunStatus:
        server_runner, port = await _start_test_server()
        try:
            final_script = tmp_path / "test_final_fail.py"
            final_script.write_text(
                script.read_text().replace("{port}", str(port)),
            )
            plan = load_test(str(final_script))
            result = await run_test(plan, quiet=True)
            return result.status
        finally:
            await server_runner.cleanup()

    status = asyncio.run(_run())
    assert status == RunStatus.THRESHOLD_FAILED
