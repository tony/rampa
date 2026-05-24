"""Executor protocol, execution state, and factory for rampa.

Executors schedule workload — they decide when to start iterations and how
many workers to use. They know nothing about protocols (HTTP, gRPC, etc.).

>>> import rampa.executors
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import queue
import time
import typing as t
from dataclasses import dataclass, field

from rampa._types import Sample, make_sample
from rampa.config import ScenarioConfig
from rampa.worker import ExecutionInfo, Worker

logger = logging.getLogger(__name__)

WorkerFn = t.Callable[[Worker], t.Awaitable[None]]
"""User-provided async function that receives a Worker and runs one iteration."""


@dataclass
class ExecutionState:
    """Shared mutable state for executor coordination.

    Parameters
    ----------
    sample_queue : queue.SimpleQueue[Sample | None]
        Queue for metric sample emission.
    abort_event : asyncio.Event
        Set to signal all executors to stop.
    worker_fn : WorkerFn
        User-provided async iteration function.
    scenario : str
        Current scenario name.
    setup_data : Any
        Data from the setup() phase.

    >>> import asyncio
    >>> state = ExecutionState(
    ...     sample_queue=queue.SimpleQueue(),
    ...     abort_event=asyncio.Event(),
    ...     worker_fn=lambda w: None,
    ...     scenario="test",
    ... )
    >>> state.scenario
    'test'
    """

    sample_queue: queue.SimpleQueue[Sample | None]
    abort_event: asyncio.Event
    worker_fn: WorkerFn
    scenario: str
    setup_data: t.Any = None
    _iteration_counter: int = field(default=0, repr=False)
    _worker_id_counter: int = field(default=0, repr=False)

    def next_iteration(self) -> int:
        """Return and increment the iteration counter.

        Returns
        -------
        int
            The current iteration number (pre-increment).
        """
        n = self._iteration_counter
        self._iteration_counter += 1
        return n

    def next_worker_id(self) -> int:
        """Return and increment the worker ID counter.

        Returns
        -------
        int
            The next worker ID.
        """
        n = self._worker_id_counter
        self._worker_id_counter += 1
        return n

    def make_worker(self) -> Worker:
        """Create a Worker for the current iteration.

        Returns
        -------
        Worker
            A fresh worker with the current execution context.
        """
        iteration = self.next_iteration()
        worker_id = self.next_worker_id()
        return Worker(
            sample_queue=self.sample_queue,
            execution=ExecutionInfo(
                worker_id=worker_id,
                scenario=self.scenario,
                iteration=iteration,
            ),
            setup_data=self.setup_data,
        )


async def run_iteration(state: ExecutionState) -> None:
    """Execute one user iteration with timing, error handling, and cleanup.

    Creates a worker, invokes the user function, emits ``iterations``,
    ``iteration_duration``, and optionally ``iteration_errors`` samples,
    then closes any HTTP resources.

    Parameters
    ----------
    state : ExecutionState
        Shared execution state providing the worker factory and sample queue.

    >>> import rampa.executors
    """
    worker = state.make_worker()
    start = time.monotonic_ns()
    try:
        try:
            await state.worker_fn(worker)
        except Exception:
            logger.warning(
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
        make_sample("iterations", 1.0, {"scenario": state.scenario}),
    )
    state.sample_queue.put(
        make_sample(
            "iteration_duration",
            elapsed_ns / 1_000_000,
            {"scenario": state.scenario},
        ),
    )


class Executor(t.Protocol):
    """Protocol for workload executors.

    Executors run iterations according to their scheduling strategy. They
    borrow workers from the execution state and call the user function.
    """

    async def run(self, state: ExecutionState) -> None:
        """Execute the workload.

        Parameters
        ----------
        state : ExecutionState
            Shared execution state.
        """
        ...


_EXECUTOR_REGISTRY: dict[str, type] = {}


def register_executor(name: str, cls: type) -> None:
    """Register an executor implementation by name.

    Parameters
    ----------
    name : str
        Executor name (e.g. ``"constant-vus"``).
    cls : type
        Executor class.

    >>> register_executor("test-exec", type("T", (), {}))
    >>> "test-exec" in _EXECUTOR_REGISTRY
    True
    """
    _EXECUTOR_REGISTRY[name] = cls


def create_executor(config: ScenarioConfig) -> t.Any:
    """Create an executor from a scenario config.

    Parameters
    ----------
    config : ScenarioConfig
        Scenario configuration with executor name.

    Returns
    -------
    Any
        An executor instance.

    Raises
    ------
    ValueError
        If the executor name is not registered.
    """
    cls = _EXECUTOR_REGISTRY.get(config.executor)
    if cls is None:
        available = sorted(_EXECUTOR_REGISTRY)
        parts = [f"unknown executor: {config.executor!r}"]
        close = difflib.get_close_matches(
            config.executor,
            available,
            n=1,
            cutoff=0.6,
        )
        if close:
            parts.append(f"did you mean {close[0]!r}?")
        parts.append(f"available: {available}")
        msg = ". ".join(parts)
        raise ValueError(msg)
    return cls(config)
