"""Tests for MCP RunRegistry."""

from __future__ import annotations

import typing as t

from rampa.events import RunResult, RunStatus
from rampa.mcp.registry import RunRecord, RunRegistry


class RegistryLifecycleFixture(t.NamedTuple):
    """Test case for registry lifecycle."""

    test_id: str
    run_id: str
    script_path: str


_LIFECYCLE_FIXTURES: list[RegistryLifecycleFixture] = [
    RegistryLifecycleFixture("basic", "run-1", "test.py"),
    RegistryLifecycleFixture("with_path", "run-2", "scripts/load.py"),
]


def test_registry_register_and_get() -> None:
    """RunRegistry stores and retrieves records by run_id."""
    reg = RunRegistry()
    rec = RunRecord(run_id="r1", script_path="t.py", started_at=0.0)
    reg.register(rec)
    assert reg.get("r1") is rec
    assert reg.get("missing") is None


def test_registry_list_all() -> None:
    """RunRegistry.list_all returns all registered records."""
    reg = RunRegistry()
    r1 = RunRecord(run_id="a", script_path="a.py", started_at=0.0)
    r2 = RunRecord(run_id="b", script_path="b.py", started_at=1.0)
    reg.register(r1)
    reg.register(r2)
    all_runs = reg.list_all()
    assert len(all_runs) == 2
    ids = {r.run_id for r in all_runs}
    assert ids == {"a", "b"}


def test_registry_complete_releases_runtime() -> None:
    """RunRegistry.complete stores result and releases runtime."""
    reg = RunRegistry()
    rec = RunRecord(run_id="r1", script_path="t.py", started_at=0.0)
    reg.register(rec)
    assert not rec.is_complete

    result = RunResult(
        run_id="r1",
        status=RunStatus.PASSED,
        snapshot=None,
        threshold_results=[],
    )
    reg.complete("r1", result)
    assert rec.is_complete
    assert rec.result is result
    assert rec.runtime is None


def test_registry_complete_nonexistent_is_noop() -> None:
    """RunRegistry.complete on missing run_id does nothing."""
    reg = RunRegistry()
    result = RunResult(
        run_id="missing",
        status=RunStatus.PASSED,
        snapshot=None,
        threshold_results=[],
    )
    reg.complete("missing", result)


def test_run_record_is_complete() -> None:
    """RunRecord.is_complete reflects result presence."""
    rec = RunRecord(run_id="r1", script_path="t.py", started_at=0.0)
    assert not rec.is_complete
    rec.result = RunResult(
        run_id="r1",
        status=RunStatus.THRESHOLD_FAILED,
        snapshot=None,
        threshold_results=[],
    )
    assert rec.is_complete
