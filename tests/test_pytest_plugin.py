"""Tests for the rampa pytest plugin."""

from __future__ import annotations

import asyncio
import typing as t

import pytest

from rampa.events import RunResult, RunStatus
from rampa.pytest_plugin import _run_plan
from rampa.worker import Worker


async def _noop_worker(w: Worker) -> None:
    """No-op worker for testing."""
    await asyncio.sleep(0.001)


async def _slow_worker(w: Worker) -> None:
    """Slow worker that takes 10ms per iteration."""
    await asyncio.sleep(0.01)


class MarkerFixture(t.NamedTuple):
    """Test case for rampa_scenario marker."""

    test_id: str
    executor: str
    vus: int
    duration: str
    expected_status: RunStatus


_MARKER_FIXTURES: list[MarkerFixture] = [
    MarkerFixture(
        test_id="constant_vus_pass",
        executor="constant-vus",
        vus=1,
        duration="200ms",
        expected_status=RunStatus.PASSED,
    ),
]


@pytest.mark.parametrize(
    list(MarkerFixture._fields),
    _MARKER_FIXTURES,
    ids=[f.test_id for f in _MARKER_FIXTURES],
)
def test_run_plan_returns_result(
    test_id: str,
    executor: str,
    vus: int,
    duration: str,
    expected_status: RunStatus,
) -> None:
    """_run_plan executes a plan and returns RunResult."""
    from rampa.config import Config, ScenarioConfig, parse_duration
    from rampa.loader import TestPlan

    plan = TestPlan(
        scenarios={
            "test": (
                ScenarioConfig(
                    executor=executor,
                    vus=vus,
                    duration=parse_duration(duration),
                ),
                _noop_worker,
            ),
        },
        config=Config(),
    )
    result = asyncio.run(_run_plan(plan))
    assert result.status == expected_status
    assert result.run_id is not None


def test_run_plan_with_passing_threshold() -> None:
    """_run_plan with a passing threshold returns PASSED."""
    from rampa.config import Config, ScenarioConfig, parse_duration
    from rampa.loader import TestPlan

    plan = TestPlan(
        scenarios={
            "test": (
                ScenarioConfig(
                    executor="constant-vus",
                    vus=1,
                    duration=parse_duration("200ms"),
                ),
                _slow_worker,
            ),
        },
        config=Config(
            thresholds={"iteration_duration": ["avg<1000"]},
        ),
    )
    result = asyncio.run(_run_plan(plan))
    assert result.status == RunStatus.PASSED


def test_run_plan_with_failing_threshold() -> None:
    """_run_plan with a failing threshold returns THRESHOLD_FAILED."""
    from rampa.config import Config, ScenarioConfig, parse_duration
    from rampa.loader import TestPlan

    plan = TestPlan(
        scenarios={
            "test": (
                ScenarioConfig(
                    executor="constant-vus",
                    vus=1,
                    duration=parse_duration("200ms"),
                ),
                _slow_worker,
            ),
        },
        config=Config(
            thresholds={"iteration_duration": ["avg<0.001"]},
        ),
    )
    result = asyncio.run(_run_plan(plan))
    assert result.status == RunStatus.THRESHOLD_FAILED
    assert any(not r.passed for r in result.threshold_results)


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=1,
    duration="200ms",
    worker_fn=_noop_worker,
)
def test_fixture_returns_result(rampa_result: RunResult) -> None:
    """rampa_result fixture runs the scenario and returns RunResult."""
    assert rampa_result.status == RunStatus.PASSED
    assert rampa_result.snapshot is not None


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
