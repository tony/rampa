"""Shared iterations executor — N VUs share a pool of M total iterations.

>>> import rampa.executors.shared_iterations
"""

from __future__ import annotations

import asyncio
import contextlib
import time

from rampa._types import make_sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor


class SharedIterationsExecutor:
    """VUs share a fixed pool of iterations.

    Parameters
    ----------
    config : ScenarioConfig
        Must include ``iterations`` and optionally ``vus``.

    >>> from rampa.config import ScenarioConfig
    >>> cfg = ScenarioConfig(
    ...     executor="shared-iterations",
    ...     vus=5,
    ...     iterations=100,
    ... )
    >>> e = SharedIterationsExecutor(cfg)
    >>> e._iterations
    100
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._vus = config.vus or 1
        self._iterations = config.iterations or 1

    async def run(self, state: ExecutionState) -> None:
        """Run iterations shared across VUs.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        remaining = self._iterations

        async def _vu() -> None:
            nonlocal remaining
            while remaining > 0 and not state.abort_event.is_set():
                remaining -= 1
                worker = state.make_worker()
                start = time.monotonic_ns()
                with contextlib.suppress(Exception):
                    await state.worker_fn(worker)
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

        async with asyncio.TaskGroup() as tg:
            for _ in range(self._vus):
                tg.create_task(_vu())


register_executor("shared-iterations", SharedIterationsExecutor)
