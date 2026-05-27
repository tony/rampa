"""unittest mixin for running rampa load tests.

Provides :class:`RampaTestCase` as a mixin for ``unittest.TestCase``.

>>> import rampa.unittest_plugin
"""

from __future__ import annotations

import asyncio
import typing as t

from rampa.config import Config, ScenarioConfig
from rampa.engine import Engine
from rampa.events import RunResult
from rampa.loader import TestPlan


class RampaTestCase:
    """Mixin that adds :meth:`run_rampa` to a ``unittest.TestCase``.

    Usage::

        class TestAPI(unittest.TestCase, RampaTestCase):
            async def worker(self, w: rampa.Worker) -> None:
                resp = await w.http.get("http://localhost/api")
                w.check(resp, {"status 200": lambda r: r.status == 200})

            def test_load(self) -> None:
                result = self.run_rampa(
                    worker_fn=self.worker,
                    executor="constant-vus",
                    vus=5,
                    duration="10s",
                    thresholds={"http_req_duration": ["p(95)<500"]},
                )
                assert result.status == RunStatus.PASSED

    >>> hasattr(RampaTestCase, 'run_rampa')
    True
    """

    def run_rampa(
        self,
        worker_fn: t.Callable[..., t.Any],
        executor: str = "constant-vus",
        vus: int = 1,
        duration: str = "30s",
        thresholds: dict[str, list[str]] | None = None,
        **kwargs: t.Any,
    ) -> RunResult:
        """Execute a load test and return the result.

        Parameters
        ----------
        worker_fn : Callable
            Async function that receives a Worker and runs one iteration.
        executor : str
            Executor type name (default: ``"constant-vus"``).
        vus : int
            Number of virtual users (default: 1).
        duration : str
            Duration string (default: ``"30s"``).
        thresholds : dict[str, list[str]] | None
            Threshold expressions per metric.
        **kwargs : Any
            Additional ScenarioConfig fields.

        Returns
        -------
        RunResult
            The completed test result.

        >>> callable(RampaTestCase.run_rampa)
        True
        """
        from rampa.config import parse_duration

        cfg = ScenarioConfig(
            executor=executor,
            vus=vus,
            duration=parse_duration(duration),
            **kwargs,
        )
        config = Config(thresholds=thresholds or {})
        plan = TestPlan(
            scenarios={"test": (cfg, worker_fn)},
            config=config,
        )
        return asyncio.run(_run_plan(plan))


async def _run_plan(plan: TestPlan) -> RunResult:
    """Execute a TestPlan through the headless engine.

    Parameters
    ----------
    plan : TestPlan
        Resolved test plan.

    Returns
    -------
    RunResult
        The completed test result.
    """
    controller = await Engine(plan).start()
    return await controller.wait()
