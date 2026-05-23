"""Constant arrival rate executor — schedules iterations at a fixed rate.

This is an open-model executor: iteration starts are decoupled from response
completion. If the system under test slows down, VUs pile up rather than
silently reducing the request rate.

>>> import rampa.executors.constant_arrival_rate
"""

from __future__ import annotations

import asyncio
import contextlib
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor


class ConstantArrivalRateExecutor:
    """Schedule iterations at a constant rate regardless of response time.

    When all VUs are busy, the iteration is counted as ``dropped_iterations``
    rather than silently reducing the arrival rate.

    Parameters
    ----------
    config : ScenarioConfig
        Must include ``rate``, ``duration``, and ``pre_allocated_vus`` or
        ``max_vus``.

    >>> from rampa.config import ScenarioConfig
    >>> import datetime
    >>> cfg = ScenarioConfig(
    ...     executor="constant-arrival-rate",
    ...     rate=10.0,
    ...     duration=datetime.timedelta(seconds=5),
    ...     pre_allocated_vus=5,
    ...     max_vus=10,
    ... )
    >>> e = ConstantArrivalRateExecutor(cfg)
    >>> e._rate
    10.0
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._rate = config.rate or 1.0
        dur = config.duration
        self._duration = dur.total_seconds() if dur is not None else 30.0
        tu = config.time_unit
        self._time_unit = tu.total_seconds() if tu is not None else 1.0
        self._max_vus = config.max_vus or config.pre_allocated_vus or 10

    async def run(self, state: ExecutionState) -> None:
        """Schedule iterations at the configured rate.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        interval = self._time_unit / self._rate
        loop = asyncio.get_event_loop()
        start = loop.time()
        sem = asyncio.Semaphore(self._max_vus)
        tick = 0
        dropped = 0

        async with asyncio.TaskGroup() as tg:
            while not state.abort_event.is_set():
                target_time = start + tick * interval
                now = loop.time()
                elapsed = now - start

                if elapsed >= self._duration:
                    break

                if now < target_time:
                    await asyncio.sleep(target_time - now)

                if sem.locked():
                    dropped += 1
                    state.sample_queue.put(
                        make_sample(
                            "dropped_iterations",
                            1.0,
                            {"scenario": state.scenario},
                        ),
                    )
                else:
                    await sem.acquire()
                    tg.create_task(
                        self._run_iteration(state, sem),
                    )

                tick += 1

    async def _run_iteration(
        self,
        state: ExecutionState,
        sem: asyncio.Semaphore,
    ) -> None:
        """Run one iteration and release the semaphore when done."""
        worker = state.make_worker()
        start = time.monotonic_ns()
        try:
            with contextlib.suppress(Exception):
                await state.worker_fn(worker)
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
            sem.release()


register_executor("constant-arrival-rate", ConstantArrivalRateExecutor)
