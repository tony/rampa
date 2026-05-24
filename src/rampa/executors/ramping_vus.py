"""Ramping VUs executor — linearly interpolates VU count between stages.

>>> import rampa.executors.ramping_vus
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor


class RampingVUsExecutor:
    """Ramp VU count linearly through configured stages.

    Parameters
    ----------
    config : ScenarioConfig
        Must include ``stages`` list.

    >>> from rampa.config import ScenarioConfig, Stage
    >>> import datetime
    >>> cfg = ScenarioConfig(
    ...     executor="ramping-vus",
    ...     stages=[
    ...         Stage(
    ...             duration=datetime.timedelta(seconds=5),
    ...             target=10,
    ...         ),
    ...     ],
    ... )
    >>> e = RampingVUsExecutor(cfg)
    >>> len(e._stages)
    1
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._stages = config.stages or []
        self._start_vus = config.vus or 0

    async def run(self, state: ExecutionState) -> None:
        """Execute ramping VU stages.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        current_vus = self._start_vus
        tasks: set[asyncio.Task[None]] = set()

        for stage in self._stages:
            if state.abort_event.is_set():
                break
            target = stage.target
            duration_s = stage.duration.total_seconds()
            steps = max(int(duration_s * 2), 1)
            step_duration = duration_s / steps
            vu_diff_per_step = (target - current_vus) / steps

            for step in range(steps):
                if state.abort_event.is_set():
                    break
                desired = int(current_vus + vu_diff_per_step * (step + 1))
                active = sum(1 for t in tasks if not t.done())

                while active < desired and not state.abort_event.is_set():
                    task = asyncio.create_task(self._run_vu(state))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                    active += 1

                await asyncio.sleep(step_duration)

            current_vus = target

        for task in list(tasks):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _run_vu(self, state: ExecutionState) -> None:
        """Single VU loop: iterate until cancelled or aborted."""
        while not state.abort_event.is_set():
            worker = state.make_worker()
            start = time.monotonic_ns()
            try:
                try:
                    await state.worker_fn(worker)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "iteration %d failed",
                        worker.execution.iteration,
                    )
                    state.sample_queue.put(
                        make_sample(
                            "iteration_errors",
                            1.0,
                            {"scenario": state.scenario},
                        ),
                    )
            finally:
                if worker._http is not None:
                    await worker._http.close()
            elapsed_ns = time.monotonic_ns() - start
            state.sample_queue.put(
                make_sample(
                    "iterations",
                    1.0,
                    {"scenario": state.scenario},
                ),
            )
            state.sample_queue.put(
                make_sample(
                    "iteration_duration",
                    elapsed_ns / 1_000_000,
                    {"scenario": state.scenario},
                ),
            )


register_executor("ramping-vus", RampingVUsExecutor)
