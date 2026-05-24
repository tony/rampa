"""Per-VU iterations executor — each VU runs exactly N iterations.

>>> import rampa.executors.per_vu_iterations
"""

from __future__ import annotations

import asyncio

from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, register_executor, run_iteration


class PerVUIterationsExecutor:
    """Each VU runs a fixed number of iterations independently.

    Parameters
    ----------
    config : ScenarioConfig
        Must include ``iterations`` and optionally ``vus``.

    >>> from rampa.config import ScenarioConfig
    >>> cfg = ScenarioConfig(
    ...     executor="per-vu-iterations",
    ...     vus=3,
    ...     iterations=10,
    ... )
    >>> e = PerVUIterationsExecutor(cfg)
    >>> e._iterations_per_vu
    10
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._vus = config.vus or 1
        self._iterations_per_vu = config.iterations or 1

    async def run(self, state: ExecutionState) -> None:
        """Run each VU for its fixed iteration count.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """

        async def _vu() -> None:
            state.vu_started()
            try:
                for _ in range(self._iterations_per_vu):
                    if state.abort_event.is_set():
                        break
                    await run_iteration(state)
            finally:
                state.vu_stopped()

        async with asyncio.TaskGroup() as tg:
            for _ in range(self._vus):
                tg.create_task(_vu())


register_executor("per-vu-iterations", PerVUIterationsExecutor)
