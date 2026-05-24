"""Tests for the rampa pytest plugin.

Uses both direct unit tests and pytester-based end-to-end tests
following pytest's canonical plugin testing patterns.
"""

from __future__ import annotations

import asyncio
import typing as t

import _pytest.pytester
import pytest

from rampa.config import Config, ScenarioConfig, parse_duration
from rampa.events import RunResult, RunStatus
from rampa.loader import TestPlan
from rampa.pytest_plugin import _run_plan
from rampa.worker import Worker

pytest_plugins = ["pytester"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop_worker(w: Worker) -> None:
    """No-op worker for testing."""
    await asyncio.sleep(0.001)


async def _slow_worker(w: Worker) -> None:
    """Slow worker that takes 10ms per iteration."""
    await asyncio.sleep(0.01)


def _make_plan(
    worker_fn: t.Callable[..., t.Any],
    executor: str = "constant-vus",
    vus: int = 1,
    duration_ms: int = 200,
    thresholds: dict[str, list[str]] | None = None,
) -> TestPlan:
    """Build a TestPlan for plugin testing."""
    return TestPlan(
        scenarios={
            "test": (
                ScenarioConfig(
                    executor=executor,
                    vus=vus,
                    duration=parse_duration(f"{duration_ms}ms"),
                ),
                worker_fn,
            ),
        },
        config=Config(thresholds=thresholds or {}),
    )


# ---------------------------------------------------------------------------
# Direct unit tests for _run_plan
# ---------------------------------------------------------------------------


class RunPlanFixture(t.NamedTuple):
    """Test case for _run_plan."""

    test_id: str
    executor: str
    vus: int
    duration_ms: int
    expected_status: RunStatus


_RUN_PLAN_FIXTURES: list[RunPlanFixture] = [
    RunPlanFixture(
        test_id="constant_vus_pass",
        executor="constant-vus",
        vus=1,
        duration_ms=200,
        expected_status=RunStatus.PASSED,
    ),
    RunPlanFixture(
        test_id="shared_iterations_pass",
        executor="shared-iterations",
        vus=1,
        duration_ms=200,
        expected_status=RunStatus.PASSED,
    ),
]


@pytest.mark.parametrize(
    list(RunPlanFixture._fields),
    _RUN_PLAN_FIXTURES,
    ids=[f.test_id for f in _RUN_PLAN_FIXTURES],
)
def test_run_plan_returns_result(
    test_id: str,
    executor: str,
    vus: int,
    duration_ms: int,
    expected_status: RunStatus,
) -> None:
    """_run_plan executes a plan and returns RunResult."""
    plan = _make_plan(
        _noop_worker,
        executor=executor,
        vus=vus,
        duration_ms=duration_ms,
    )
    result = asyncio.run(_run_plan(plan))
    assert result.status == expected_status
    assert result.run_id is not None
    assert len(result.run_id) > 0


def test_run_plan_with_passing_threshold() -> None:
    """_run_plan with a passing threshold returns PASSED."""
    plan = _make_plan(
        _slow_worker,
        thresholds={"iteration_duration": ["avg<1000"]},
    )
    result = asyncio.run(_run_plan(plan))
    assert result.status == RunStatus.PASSED
    assert len(result.threshold_results) > 0
    assert all(r.passed for r in result.threshold_results)


def test_run_plan_with_failing_threshold() -> None:
    """_run_plan with a failing threshold returns THRESHOLD_FAILED."""
    plan = _make_plan(
        _slow_worker,
        thresholds={"iteration_duration": ["avg<0.001"]},
    )
    result = asyncio.run(_run_plan(plan))
    assert result.status == RunStatus.THRESHOLD_FAILED
    assert any(not r.passed for r in result.threshold_results)


def test_run_plan_snapshot_present() -> None:
    """_run_plan result includes a metric snapshot."""
    plan = _make_plan(_noop_worker)
    result = asyncio.run(_run_plan(plan))
    assert result.snapshot is not None
    assert result.snapshot.duration > 0


# ---------------------------------------------------------------------------
# Fixture integration tests (using marker + fixture directly)
# ---------------------------------------------------------------------------


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=1,
    duration="200ms",
    worker_fn=_noop_worker,
)
def test_fixture_returns_result(rampa_result: RunResult) -> None:
    """rampa_result fixture runs the scenario and returns RunResult."""
    assert isinstance(rampa_result, RunResult)
    assert rampa_result.status == RunStatus.PASSED
    assert rampa_result.snapshot is not None
    assert rampa_result.run_id is not None


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=2,
    duration="200ms",
    worker_fn=_noop_worker,
)
def test_fixture_multiple_vus(rampa_result: RunResult) -> None:
    """rampa_result fixture works with multiple VUs."""
    assert rampa_result.status == RunStatus.PASSED
    assert rampa_result.snapshot is not None
    iterations = rampa_result.snapshot.values.get("iterations", {})
    assert iterations.get("count", 0) > 0


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=1,
    duration="200ms",
    worker_fn=_slow_worker,
    thresholds={"iteration_duration": ["avg<1000"]},
)
def test_fixture_with_passing_threshold(rampa_result: RunResult) -> None:
    """rampa_result fixture passes when thresholds are met."""
    assert rampa_result.status == RunStatus.PASSED
    assert len(rampa_result.threshold_results) > 0


@pytest.mark.rampa_scenario(
    executor="shared-iterations",
    vus=2,
    iterations=10,
    worker_fn=_noop_worker,
)
def test_fixture_shared_iterations(rampa_result: RunResult) -> None:
    """rampa_result fixture works with shared-iterations executor."""
    assert rampa_result.status == RunStatus.PASSED
    assert rampa_result.snapshot is not None


# ---------------------------------------------------------------------------
# Pytester end-to-end tests
# ---------------------------------------------------------------------------


def test_marker_registered(pytester: _pytest.pytester.Pytester) -> None:
    """Plugin registers the rampa_scenario marker."""
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*rampa_scenario*"])


def test_fixture_skips_without_marker(
    pytester: _pytest.pytester.Pytester,
) -> None:
    """rampa_result fixture skips when marker is absent."""
    pytester.makepyfile("""
        def test_no_marker(rampa_result):
            pass
    """)
    result = pytester.runpytest("-v")
    result.assert_outcomes(skipped=1)


def test_fixture_skips_without_worker_fn(
    pytester: _pytest.pytester.Pytester,
) -> None:
    """rampa_result fixture skips when worker_fn is missing from marker."""
    pytester.makepyfile("""
        import pytest

        @pytest.mark.rampa_scenario(executor="constant-vus", vus=1, duration="100ms")
        def test_no_worker(rampa_result):
            pass
    """)
    result = pytester.runpytest("-v")
    result.assert_outcomes(skipped=1)


def test_e2e_passing_scenario(
    pytester: _pytest.pytester.Pytester,
) -> None:
    """End-to-end: passing scenario via pytester."""
    pytester.makepyfile("""
        import asyncio
        import pytest
        from rampa.events import RunResult, RunStatus

        async def worker(w):
            await asyncio.sleep(0.001)

        @pytest.mark.rampa_scenario(
            executor="constant-vus",
            vus=1,
            duration="200ms",
            worker_fn=worker,
        )
        def test_pass(rampa_result: RunResult) -> None:
            assert rampa_result.status == RunStatus.PASSED
    """)
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)


def test_e2e_threshold_failure_detected(
    pytester: _pytest.pytester.Pytester,
) -> None:
    """End-to-end: threshold failure detected in test body assertion."""
    pytester.makepyfile("""
        import asyncio
        import pytest
        from rampa.events import RunResult, RunStatus

        async def slow_worker(w):
            await asyncio.sleep(0.01)

        @pytest.mark.rampa_scenario(
            executor="constant-vus",
            vus=1,
            duration="200ms",
            worker_fn=slow_worker,
            thresholds={"iteration_duration": ["avg<0.001"]},
        )
        def test_threshold_breach(rampa_result: RunResult) -> None:
            assert rampa_result.status == RunStatus.PASSED
    """)
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)


def test_e2e_threshold_results_accessible(
    pytester: _pytest.pytester.Pytester,
) -> None:
    """End-to-end: threshold results are accessible in RunResult."""
    pytester.makepyfile("""
        import asyncio
        import pytest
        from rampa.events import RunResult, RunStatus

        async def slow_worker(w):
            await asyncio.sleep(0.01)

        @pytest.mark.rampa_scenario(
            executor="constant-vus",
            vus=1,
            duration="200ms",
            worker_fn=slow_worker,
            thresholds={"iteration_duration": ["avg<0.001"]},
        )
        def test_results(rampa_result: RunResult) -> None:
            assert rampa_result.status == RunStatus.THRESHOLD_FAILED
            failed = [r for r in rampa_result.threshold_results if not r.passed]
            assert len(failed) > 0
    """)
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)


def test_e2e_multiple_tests_in_one_file(
    pytester: _pytest.pytester.Pytester,
) -> None:
    """End-to-end: multiple rampa tests in one file run independently."""
    pytester.makepyfile("""
        import asyncio
        import pytest
        from rampa.events import RunResult, RunStatus

        async def worker(w):
            await asyncio.sleep(0.001)

        @pytest.mark.rampa_scenario(
            executor="constant-vus", vus=1, duration="100ms",
            worker_fn=worker,
        )
        def test_first(rampa_result: RunResult) -> None:
            assert rampa_result.status == RunStatus.PASSED

        @pytest.mark.rampa_scenario(
            executor="constant-vus", vus=2, duration="100ms",
            worker_fn=worker,
        )
        def test_second(rampa_result: RunResult) -> None:
            assert rampa_result.status == RunStatus.PASSED
    """)
    result = pytester.runpytest("-v", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=2)
