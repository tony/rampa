"""Tests for MCP tools using synthetic test plans."""

from __future__ import annotations

import asyncio
import typing as t

import pytest

from rampa.mcp.tools.runs import (
    get_status_impl,
    list_runs_impl,
    start_run_impl,
    stop_run_impl,
)


def _make_test_script(tmp_path: t.Any) -> str:
    """Create a minimal test script for MCP tool testing."""
    script = tmp_path / "mcp_test.py"
    script.write_text(
        "from __future__ import annotations\n"
        "import rampa\n"
        "\n"
        '@rampa.scenario(executor="constant-vus", vus=1, duration="200ms")\n'
        "async def default(worker: rampa.Worker) -> None:\n"
        "    import asyncio\n"
        "    await asyncio.sleep(0.01)\n",
    )
    return str(script)


def test_start_run_returns_run_id(tmp_path: t.Any) -> None:
    """start_run creates a run and returns a run_id."""

    async def _run() -> dict[str, str]:
        script = _make_test_script(tmp_path)
        result = await start_run_impl(script)
        return result

    result = asyncio.run(_run())
    assert "run_id" in result
    assert result["status"] == "started"


def test_start_run_invalid_script() -> None:
    """start_run returns error for nonexistent script."""

    async def _run() -> dict[str, str]:
        return await start_run_impl("/nonexistent/path.py")

    result = asyncio.run(_run())
    assert "error" in result


def test_list_runs_includes_started(tmp_path: t.Any) -> None:
    """list_runs includes a recently started run."""

    async def _run() -> list[dict[str, str]]:
        script = _make_test_script(tmp_path)
        await start_run_impl(script)
        return await list_runs_impl()

    runs = asyncio.run(_run())
    assert len(runs) >= 1
    assert any(r["status"] in {"running", "passed"} for r in runs)


def test_get_status_running(tmp_path: t.Any) -> None:
    """get_status returns running status for active run."""

    async def _run() -> dict[str, t.Any]:
        script = _make_test_script(tmp_path)
        start_result = await start_run_impl(script)
        run_id = start_result["run_id"]
        return await get_status_impl(run_id)

    status = asyncio.run(_run())
    assert status["run_id"] is not None
    assert status.get("status") in {"running", "passed"}


def test_get_status_not_found() -> None:
    """get_status returns error for unknown run_id."""

    async def _run() -> dict[str, t.Any]:
        return await get_status_impl("nonexistent-id")

    result = asyncio.run(_run())
    assert "error" in result


def test_stop_run_not_found() -> None:
    """stop_run returns error for unknown run_id."""

    async def _run() -> dict[str, str]:
        return await stop_run_impl("nonexistent-id")

    result = asyncio.run(_run())
    assert "error" in result


class ReadOnlyHintCase(t.NamedTuple):
    """A tool and the ``readOnlyHint`` it must advertise."""

    test_id: str
    tool_name: str
    read_only: bool


_READ_ONLY_HINT_CASES: list[ReadOnlyHintCase] = [
    ReadOnlyHintCase("start_run", "start_run", False),
    ReadOnlyHintCase("stop_run", "stop_run", False),
    ReadOnlyHintCase("pause_run", "pause_run", False),
    ReadOnlyHintCase("resume_run", "resume_run", False),
    ReadOnlyHintCase("get_status", "get_status", True),
    ReadOnlyHintCase("list_runs", "list_runs", True),
    ReadOnlyHintCase("discover_scenarios", "discover_scenarios", True),
    ReadOnlyHintCase("inspect_config", "inspect_config", True),
    ReadOnlyHintCase("get_metrics", "get_metrics", True),
    ReadOnlyHintCase("get_thresholds", "get_thresholds", True),
]


@pytest.mark.parametrize(
    "case",
    _READ_ONLY_HINT_CASES,
    ids=lambda case: case.test_id,
)
def test_tool_advertises_read_only_hint(case: ReadOnlyHintCase) -> None:
    """Every tool declares whether calling it changes state.

    The hint reaches MCP clients, which use it to decide whether a call
    needs confirmation, and the documentation renders its risk badge from
    the same value.
    """
    from fastmcp import Client

    from rampa.mcp.server import build_mcp_server

    async def _hints() -> dict[str, bool | None]:
        async with Client(build_mcp_server()) as client:
            return {
                tool.name: getattr(tool.annotations, "read_only_hint", None)
                for tool in await client.list_tools()
            }

    assert asyncio.run(_hints())[case.tool_name] is case.read_only
