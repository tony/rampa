"""Constant VUs executor — runs N workers for a fixed duration.

This is a closed-model executor: each worker waits for the previous
iteration to complete before starting the next one.

>>> import rampa.executors.constant_vus
"""

from __future__ import annotations

import asyncio
import logging
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor


class ConstantVUsExecutor:
    """Run a fixed number of VUs for a specified duration.

    Parameters
    ----------
    config : ScenarioConfig
        Must include ``vus`` and ``duration``.

    >>> from rampa.config import ScenarioConfig
    >>> import datetime
    >>> cfg = ScenarioConfig(
    ...     executor="constant-vus",
    ...     vus=5,
    ...     duration=datetime.timedelta(seconds=10),
    ... )
    >>> e = ConstantVUsExecutor(cfg)
    >>> e._vus
    5
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._vus = config.vus or 1
        dur = config.duration
        self._duration = dur.total_seconds() if dur is not None else 30.0

    async def run(self, state: ExecutionState) -> None:
        """Run VU workers for the configured duration.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        async with asyncio.TaskGroup() as tg:
            for _ in range(self._vus):
                tg.create_task(self._run_vu(state))

    async def _run_vu(self, state: ExecutionState) -> None:
        """Single VU loop: iterate until duration expires or abort."""
        deadline = asyncio.get_event_loop().time() + self._duration
        loop = asyncio.get_event_loop()

        while loop.time() < deadline and not state.abort_event.is_set():
            worker = state.make_worker()
            start = time.monotonic_ns()
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
            elapsed_ns = time.monotonic_ns() - start
            state.sample_queue.put(
                make_sample("iterations", 1.0, {"scenario": state.scenario}),
            )
            state.sample_queue.put(
                make_sample(
                    "iteration_duration",
                    elapsed_ns / 1_000_000,
                    {"scenario": state.scenario},
                ),
            )


register_executor("constant-vus", ConstantVUsExecutor)
