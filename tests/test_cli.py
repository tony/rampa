"""Tests for rampa CLI commands: check and doctor."""

from __future__ import annotations

import textwrap
import typing as t

import pytest
from click.testing import CliRunner

from rampa.cli import main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class CheckFixture(t.NamedTuple):
    """Test case for rampa check command."""

    test_id: str
    script_content: str
    expected_exit_code: int
    expected_output: str


_CHECK_FIXTURES: list[CheckFixture] = [
    CheckFixture(
        test_id="valid_script",
        script_content=textwrap.dedent("""\
            import asyncio
            import rampa

            @rampa.scenario(executor="constant-vus", vus=2, duration="1s")
            async def default(w):
                await asyncio.sleep(0.001)
        """),
        expected_exit_code=0,
        expected_output="status: valid",
    ),
    CheckFixture(
        test_id="no_scenarios",
        script_content=textwrap.dedent("""\
            async def helper():
                pass
        """),
        expected_exit_code=1,
        expected_output="error:",
    ),
]


# ---------------------------------------------------------------------------
# Tests: check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(CheckFixture._fields),
    _CHECK_FIXTURES,
    ids=[f.test_id for f in _CHECK_FIXTURES],
)
def test_check_command(
    test_id: str,
    script_content: str,
    expected_exit_code: int,
    expected_output: str,
    tmp_path: t.Any,
) -> None:
    """Rampa check validates scripts and reports status."""
    script = tmp_path / "test_script.py"
    script.write_text(script_content)

    runner = CliRunner()
    result = runner.invoke(main, ["check", str(script)])
    assert result.exit_code == expected_exit_code
    assert expected_output in result.output or expected_output in (result.stderr or "")


def test_check_missing_file() -> None:
    """Rampa check fails for nonexistent script."""
    runner = CliRunner()
    result = runner.invoke(main, ["check", "/nonexistent/script.py"])
    assert result.exit_code != 0


def test_check_shows_scenario_details(tmp_path: t.Any) -> None:
    """Rampa check displays scenario executor, VUs, and duration."""
    script = tmp_path / "test_details.py"
    script.write_text(
        textwrap.dedent("""\
        import asyncio
        import rampa

        @rampa.scenario(executor="constant-vus", vus=5, duration="30s")
        async def default(w):
            await asyncio.sleep(0.001)
    """)
    )

    runner = CliRunner()
    result = runner.invoke(main, ["check", str(script)])
    assert result.exit_code == 0
    assert "constant-vus" in result.output
    assert "5 VUs" in result.output
    assert "30s" in result.output


# ---------------------------------------------------------------------------
# Tests: doctor
# ---------------------------------------------------------------------------


def test_doctor_exits_zero() -> None:
    """Rampa doctor always exits 0."""
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0


def test_doctor_shows_python_version() -> None:
    """Rampa doctor reports Python version."""
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert "python:" in result.output


def test_doctor_shows_aiohttp() -> None:
    """Rampa doctor reports aiohttp version."""
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert "aiohttp:" in result.output


# ---------------------------------------------------------------------------
# Tests: --event-log
# ---------------------------------------------------------------------------


def test_event_log_produces_jsonl(tmp_path: t.Any) -> None:
    """--event-log writes a JSONL file with PhaseEvent lines."""
    script = tmp_path / "test_log.py"
    script.write_text(
        textwrap.dedent("""\
        import asyncio
        import rampa

        @rampa.scenario(executor="constant-vus", vus=1, duration="200ms")
        async def default(w):
            await asyncio.sleep(0.001)
    """),
    )
    log_file = tmp_path / "events.jsonl"

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["run", str(script), "--event-log", str(log_file), "--quiet"],
    )
    assert result.exit_code == 0, result.output

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) > 0

    import json

    events = [json.loads(line) for line in lines]
    types = [e["type"] for e in events]
    assert "PhaseEvent" in types

    phase_events = [e for e in events if e["type"] == "PhaseEvent"]
    phases = [e["phase"] for e in phase_events]
    assert "setup" in phases
    assert "execute" in phases
    assert "teardown" in phases
    assert "complete" in phases


def test_event_log_contains_snapshot_events(tmp_path: t.Any) -> None:
    """--event-log includes SnapshotEvent entries with metric values."""
    script = tmp_path / "test_snap.py"
    script.write_text(
        textwrap.dedent("""\
        import asyncio
        import rampa

        @rampa.scenario(executor="constant-vus", vus=1, duration="200ms")
        async def default(w):
            await asyncio.sleep(0.01)
    """),
    )
    log_file = tmp_path / "events.jsonl"

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["run", str(script), "--event-log", str(log_file), "--quiet"],
    )
    assert result.exit_code == 0, result.output

    import json

    lines = log_file.read_text().strip().splitlines()
    events = [json.loads(line) for line in lines]
    snapshots = [e for e in events if e["type"] == "SnapshotEvent"]
    assert len(snapshots) > 0
    assert "snapshot" in snapshots[0]
    assert "values" in snapshots[0]["snapshot"]
