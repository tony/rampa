"""Tests for rampa CLI commands.

>>> import tests.test_cli
"""

from __future__ import annotations

import contextlib
import json
import textwrap
import typing as t

import pytest

from rampa.cli import main

if t.TYPE_CHECKING:
    type ExpectedOutput = str | list[str] | None


class CLIFixture(t.NamedTuple):
    """Test case for rampa CLI subcommands."""

    test_id: str
    cli_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


_CLI_FIXTURES: list[CLIFixture] = [
    CLIFixture(
        test_id="no-args",
        cli_args=[],
        expected_exit_code=0,
        expected_in_out=["rampa", "run", "check", "doctor"],
    ),
    CLIFixture(
        test_id="--help",
        cli_args=["--help"],
        expected_exit_code=0,
        expected_in_out=["run", "check", "doctor"],
    ),
    CLIFixture(
        test_id="-h",
        cli_args=["-h"],
        expected_exit_code=0,
        expected_in_out=["run", "check", "doctor"],
    ),
    CLIFixture(
        test_id="--version",
        cli_args=["--version"],
        expected_exit_code=0,
        expected_in_out="rampa",
    ),
    CLIFixture(
        test_id="-V",
        cli_args=["-V"],
        expected_exit_code=0,
        expected_in_out="rampa",
    ),
    CLIFixture(
        test_id="run--help",
        cli_args=["run", "--help"],
        expected_exit_code=0,
        expected_in_out=["--vus", "--duration", "--scenario"],
        expected_not_in_out="--version",
    ),
    CLIFixture(
        test_id="check--help",
        cli_args=["check", "--help"],
        expected_exit_code=0,
        expected_in_out="script",
        expected_not_in_out="--version",
    ),
    CLIFixture(
        test_id="doctor",
        cli_args=["doctor"],
        expected_exit_code=0,
        expected_in_out="python:",
    ),
    CLIFixture(
        test_id="doctor--help",
        cli_args=["doctor", "--help"],
        expected_exit_code=0,
        expected_in_out="runtime environment",
    ),
]


def _normalize_needles(value: ExpectedOutput) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


@pytest.mark.parametrize(
    list(CLIFixture._fields),
    _CLI_FIXTURES,
    ids=[f.test_id for f in _CLI_FIXTURES],
)
def test_cli(
    test_id: str,
    cli_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test rampa CLI subcommands."""
    monkeypatch.setenv("NO_COLOR", "1")

    exit_code = 0
    try:
        main(cli_args)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0

    assert exit_code == expected_exit_code

    result = capsys.readouterr()

    for needle in _normalize_needles(expected_in_out):
        assert needle in result.out, f"Expected {needle!r} in stdout: {result.out!r}"

    for needle in _normalize_needles(expected_not_in_out):
        assert needle not in result.out, f"Expected {needle!r} NOT in stdout: {result.out!r}"

    for needle in _normalize_needles(expected_in_err):
        assert needle in result.err, f"Expected {needle!r} in stderr: {result.err!r}"

    for needle in _normalize_needles(expected_not_in_err):
        assert needle not in result.err, f"Expected {needle!r} NOT in stderr: {result.err!r}"


# ---------------------------------------------------------------------------
# Tests: check
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
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rampa check validates scripts and reports status."""
    monkeypatch.setenv("NO_COLOR", "1")
    script = tmp_path / "test_script.py"
    script.write_text(script_content)

    exit_code = 0
    try:
        main(["check", str(script)])
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0

    result = capsys.readouterr()
    assert exit_code == expected_exit_code
    assert expected_output in result.out or expected_output in result.err


def test_check_missing_file(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rampa check fails for nonexistent script."""
    monkeypatch.setenv("NO_COLOR", "1")
    exit_code = 0
    try:
        main(["check", "/nonexistent/script.py"])
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0
    assert exit_code != 0


def test_check_shows_scenario_details(
    tmp_path: t.Any,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rampa check displays scenario executor, VUs, and duration."""
    monkeypatch.setenv("NO_COLOR", "1")
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

    with contextlib.suppress(SystemExit):
        main(["check", str(script)])

    result = capsys.readouterr()
    assert "constant-vus" in result.out
    assert "5 VUs" in result.out
    assert "30s" in result.out


# ---------------------------------------------------------------------------
# Tests: doctor
# ---------------------------------------------------------------------------


def test_doctor_exits_zero(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rampa doctor always exits 0."""
    monkeypatch.setenv("NO_COLOR", "1")
    exit_code = 0
    try:
        main(["doctor"])
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0
    assert exit_code == 0


def test_doctor_shows_python_version(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rampa doctor reports Python version."""
    monkeypatch.setenv("NO_COLOR", "1")
    with contextlib.suppress(SystemExit):
        main(["doctor"])
    result = capsys.readouterr()
    assert "python:" in result.out


def test_doctor_shows_aiohttp(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rampa doctor reports aiohttp version."""
    monkeypatch.setenv("NO_COLOR", "1")
    with contextlib.suppress(SystemExit):
        main(["doctor"])
    result = capsys.readouterr()
    assert "aiohttp:" in result.out


# ---------------------------------------------------------------------------
# Tests: --event-log
# ---------------------------------------------------------------------------


def test_event_log_produces_jsonl(
    tmp_path: t.Any,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--event-log writes a JSONL file with PhaseEvent lines."""
    monkeypatch.setenv("NO_COLOR", "1")
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

    exit_code = 0
    try:
        main(["run", str(script), "--event-log", str(log_file), "--quiet"])
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0
    assert exit_code == 0

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) > 0

    events = [json.loads(line) for line in lines]
    types = [e["type"] for e in events]
    assert "PhaseEvent" in types

    phase_events = [e for e in events if e["type"] == "PhaseEvent"]
    phases = [e["phase"] for e in phase_events]
    assert "setup" in phases
    assert "execute" in phases
    assert "teardown" in phases
    assert "complete" in phases


def test_event_log_contains_snapshot_events(
    tmp_path: t.Any,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--event-log includes SnapshotEvent entries with metric values."""
    monkeypatch.setenv("NO_COLOR", "1")
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

    exit_code = 0
    try:
        main(["run", str(script), "--event-log", str(log_file), "--quiet"])
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 0
    assert exit_code == 0

    lines = log_file.read_text().strip().splitlines()
    events = [json.loads(line) for line in lines]
    snapshots = [e for e in events if e["type"] == "SnapshotEvent"]
    assert len(snapshots) > 0
    assert "snapshot" in snapshots[0]
    assert "values" in snapshots[0]["snapshot"]
