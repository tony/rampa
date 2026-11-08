"""Constant arrival rate executor — schedules iterations at a fixed rate.

This is an open-model executor: iteration starts are decoupled from response
completion. If the system under test slows down, VUs pile up rather than
silently reducing the request rate.

>>> import rampa.executors.constant_arrival_rate
"""

from __future__ import annotations

import asyncio
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor, run_iteration
from rampa.rate_controller import RateController


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

        Delegates deadline arithmetic to a ``RateController`` (Python or
        Rust). Batch-admits all due ticks per wake cycle. Dropped
        iterations consume their timeslot to avoid cascading drops.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        interval_s = self._time_unit / self._rate
        interval_ns = int(interval_s * 1_000_000_000)
        start_ns = time.monotonic_ns()
        end_ns = start_ns + int(self._duration * 1_000_000_000)
        sem = asyncio.Semaphore(self._max_vus)

        controller = RateController(start_ns, interval_ns)

        async with asyncio.TaskGroup() as tg:
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
                        tg.create_task(
                            self._run_iteration(state, sem),
                        )

                if next_deadline_ns >= end_ns:
                    break

                sleep_s = max(0, (next_deadline_ns - time.monotonic_ns())) / 1_000_000_000
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

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


register_executor("constant-arrival-rate", ConstantArrivalRateExecutor)
