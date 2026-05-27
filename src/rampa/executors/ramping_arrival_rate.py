"""Ramping arrival rate executor — interpolates arrival rate between stages.

>>> import rampa.executors.ramping_arrival_rate
"""

from __future__ import annotations

import asyncio
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor, run_iteration
from rampa.rate_controller import RampingRateController


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

        Delegates deadline arithmetic to a ``RampingRateController``
        (Python or Rust) per stage. Batch-admits all due ticks per
        wake cycle.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        sem = asyncio.Semaphore(self._max_vus)
        current_rate = self._start_rate
        time_unit_ns = self._time_unit * 1_000_000_000

        async with asyncio.TaskGroup() as tg:
            for stage in self._stages:
                if state.abort_event.is_set():
                    break
                target_rate = float(stage.target)
                duration_ns = int(stage.duration.total_seconds() * 1_000_000_000)
                stage_start_ns = time.monotonic_ns()
                end_ns = stage_start_ns + duration_ns

                controller = RampingRateController(
                    stage_start_ns,
                    duration_ns,
                    current_rate,
                    target_rate,
                    time_unit_ns,
                )

                while not state.abort_event.is_set():
                    now_ns = time.monotonic_ns()
                    if now_ns >= end_ns:
                        break

                    due, next_deadline_ns = controller.advance(now_ns)

                    for _ in range(due):
                        if state.abort_event.is_set():
                            break
                        if sem.locked():
                            state.sample_queue.put(
                                make_sample(
                                    "dropped_iterations",
                                    1.0,
                                    {"scenario": state.scenario},
                                ),
                            )
                        else:
                            await sem.acquire()
                            tg.create_task(self._run_iteration(state, sem))

                    if next_deadline_ns >= end_ns:
                        break

                    sleep_s = max(0, (next_deadline_ns - time.monotonic_ns())) / 1_000_000_000
                    if sleep_s > 0:
                        await asyncio.sleep(sleep_s)

                current_rate = target_rate

    async def _run_iteration(
        self,
        state: ExecutionState,
        sem: asyncio.Semaphore,
    ) -> None:
        """Run one iteration and release the semaphore when done."""
        state.vu_started()
        try:
            await run_iteration(state)
        finally:
            state.vu_stopped()
            sem.release()


register_executor("ramping-arrival-rate", RampingArrivalRateExecutor)
