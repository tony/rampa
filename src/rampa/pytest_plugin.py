"""Pytest plugin for rampa load testing.

Register via entry point or ``pytest_plugins = ["rampa.pytest_plugin"]``.

Provides:
- ``@pytest.mark.rampa_scenario`` marker for scenario configuration
- ``rampa_result`` fixture that runs the scenario and returns ``RunResult``
- Automatic threshold failure → test failure mapping

>>> import rampa.pytest_plugin
"""

from __future__ import annotations

import asyncio
import typing as t

import pytest

from rampa.config import Config, ScenarioConfig
from rampa.engine import Engine
from rampa.events import RunResult
from rampa.loader import TestPlan


def pytest_configure(config: t.Any) -> None:
    """Register the rampa_scenario marker."""
    config.addinivalue_line(
        "markers",
        "rampa_scenario(**kwargs): configure a rampa load test scenario. "
        "Kwargs: executor, vus, duration, iterations, rate, max_vus, "
        "thresholds (dict[str, list[str]])",
    )


@pytest.fixture
def rampa_result(request: pytest.FixtureRequest) -> RunResult:
    """Run a rampa scenario defined by ``@pytest.mark.rampa_scenario``.

    The marker accepts the same kwargs as ``ScenarioConfig`` plus an
    optional ``thresholds`` dict. The fixture runs the scenario, waits
    for completion, and returns the ``RunResult``.

    If thresholds are configured and any fail, the test fails with a
    descriptive message.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object.

    Returns
    -------
    RunResult
        The completed test run result.

    Examples
    --------
    .. code-block:: python

        @pytest.mark.rampa_scenario(
            executor="constant-vus", vus=2, duration="500ms",
        )
        def test_my_api(rampa_result: RunResult) -> None:
            assert rampa_result.status == RunStatus.PASSED
    """
    marker = request.node.get_closest_marker("rampa_scenario")
    if marker is None:
        pytest.skip("no @pytest.mark.rampa_scenario marker found")

    kwargs = dict(marker.kwargs)
    thresholds: dict[str, list[str]] = kwargs.pop("thresholds", {})

    worker_fn = kwargs.pop("worker_fn", None)
    if worker_fn is None:
        pytest.skip("rampa_scenario marker requires worker_fn kwarg")

    if "duration" in kwargs and isinstance(kwargs["duration"], str):
        from rampa.config import parse_duration

        kwargs["duration"] = parse_duration(kwargs["duration"])

    scenario_config = ScenarioConfig(**kwargs)
    config = Config(thresholds=thresholds)

    plan = TestPlan(
        scenarios={"test": (scenario_config, worker_fn)},
        config=config,
    )

    return asyncio.run(_run_plan(plan))


async def _run_plan(plan: TestPlan) -> RunResult:
    """Run a test plan through the headless engine."""
    controller = await Engine(plan).start()
    return await controller.wait()
