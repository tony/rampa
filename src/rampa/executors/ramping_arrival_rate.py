"""Ramping arrival rate executor — interpolates arrival rate between stages.

>>> import rampa.executors.ramping_arrival_rate
"""

from __future__ import annotations

import asyncio
import logging
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor


class RampingArrivalRateExecutor:
    """Ramp arrival rate linearly through configured stages.

    Parameters
    ----------
    config : ScenarioConfig
        Must include ``stages``, ``pre_allocated_vus`` or ``max_vus``,
        and optionally ``rate`` for the start rate.

    >>> from rampa.config import ScenarioConfig, Stage
    >>> import datetime
    >>> cfg = ScenarioConfig(
    ...     executor="ramping-arrival-rate",
    ...     rate=10.0,
    ...     stages=[
    ...         Stage(
    ...             duration=datetime.timedelta(seconds=5),
    ...             target=100,
    ...         ),
    ...     ],
    ...     max_vus=20,
    ... )
    >>> e = RampingArrivalRateExecutor(cfg)
    >>> e._start_rate
    10.0
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._start_rate = config.rate or 1.0
        self._stages = config.stages or []
        tu = config.time_unit
        self._time_unit = tu.total_seconds() if tu is not None else 1.0
        self._max_vus = config.max_vus or config.pre_allocated_vus or 10

    async def run(self, state: ExecutionState) -> None:
        """Execute ramping arrival-rate stages.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        sem = asyncio.Semaphore(self._max_vus)
        current_rate = self._start_rate
        loop = asyncio.get_running_loop()

        async with asyncio.TaskGroup() as tg:
            for stage in self._stages:
                if state.abort_event.is_set():
                    break
                target_rate = float(stage.target)
                duration_s = stage.duration.total_seconds()
                stage_start = loop.time()
                target_time = stage_start

                while not state.abort_event.is_set():
                    elapsed = loop.time() - stage_start
                    if elapsed >= duration_s:
                        break
                    progress = elapsed / duration_s if duration_s > 0 else 1.0
                    rate = current_rate + (target_rate - current_rate) * progress
                    rate = max(rate, 0.1)
                    interval = self._time_unit / rate

                    target_time += interval
                    now = loop.time()
                    if now < target_time:
                        await asyncio.sleep(target_time - now)

                    if sem.locked():
                        state.sample_queue.put(
                            make_sample(
                                "dropped_iterations",
                                1.0,
                                {"scenario": state.scenario},
                            ),
                        )
                        await asyncio.sleep(0)
                    else:
                        await sem.acquire()
                        tg.create_task(self._run_iteration(state, sem))

                current_rate = target_rate

    async def _run_iteration(
        self,
        state: ExecutionState,
        sem: asyncio.Semaphore,
    ) -> None:
        """Run one iteration and release the semaphore when done."""
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
            await worker.http.close()
            sem.release()


register_executor("ramping-arrival-rate", RampingArrivalRateExecutor)
