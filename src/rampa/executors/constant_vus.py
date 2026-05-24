"""Constant VUs executor — runs N workers for a fixed duration.

This is a closed-model executor: each worker waits for the previous
iteration to complete before starting the next one.

>>> import rampa.executors.constant_vus
"""

from __future__ import annotations

import asyncio

from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor, run_iteration


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
        deadline = asyncio.get_running_loop().time() + self._duration
        loop = asyncio.get_running_loop()

        while loop.time() < deadline and not state.abort_event.is_set():
            await run_iteration(state)


register_executor("constant-vus", ConstantVUsExecutor)
