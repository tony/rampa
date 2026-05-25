"""Worker object passed to user scenario functions.

The Worker provides a scoped API surface for one iteration. It holds
references to the sample queue for metric emission and provides check
and custom metric helpers.

>>> import rampa.worker
"""

from __future__ import annotations

import queue
import typing as t
from dataclasses import dataclass

from rampa._types import Sample, make_sample
from rampa.http import HttpClient


@dataclass(frozen=True)
class ExecutionInfo:
    """Execution context for the current worker iteration.

    >>> info = ExecutionInfo(worker_id=1, scenario="load", iteration=0)
    >>> info.worker_id
    1
    """

    worker_id: int
    scenario: str
    iteration: int


class Worker:
    """Scoped API surface for user code within a single iteration.

    Workers are created per-iteration by the executor. They provide
    check(), counter(), gauge(), and trend() methods that emit metric
    samples to the engine's sample queue.

    Parameters
    ----------
    sample_queue : queue.SimpleQueue[Sample | None]
        Queue for emitting metric samples.
    execution : ExecutionInfo
        Current execution context.
    setup_data : Any
        Data returned from the setup() function.

    Examples
    --------
    >>> import queue as q
    >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
    >>> w = Worker(
    ...     sample_queue=sq,
    ...     execution=ExecutionInfo(worker_id=1, scenario="s", iteration=0),
    ... )
    >>> w.execution.worker_id
    1
    """

    def __init__(
        self,
        sample_queue: queue.SimpleQueue[Sample | None],
        execution: ExecutionInfo,
        setup_data: t.Any = None,
    ) -> None:
        self._queue = sample_queue
        self.execution = execution
        self.setup_data = setup_data
        self._http: HttpClient | None = None

    @property
    def http(self) -> HttpClient:
        """Lazily-initialized HTTP client with automatic metric emission.

        The client is created on first access, so non-HTTP scenarios
        never allocate an aiohttp session.

        >>> import queue as q
        >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
        >>> w = Worker(
        ...     sample_queue=sq,
        ...     execution=ExecutionInfo(
        ...         worker_id=1, scenario="s", iteration=0,
        ...     ),
        ... )
        >>> w._http is None
        True
        >>> client = w.http
        >>> w._http is not None
        True
        """
        if self._http is None:
            self._http = HttpClient(
                self._queue,
                {"scenario": self.execution.scenario},
            )
        return self._http

    def _emit(self, sample: Sample) -> None:
        """Push a sample to the metric engine queue."""
        self._queue.put(sample)

    def check(
        self,
        value: t.Any,
        conditions: dict[str, t.Callable[[t.Any], bool]],
    ) -> bool:
        """Evaluate named conditions and emit check metric samples.

        Each condition emits one sample on the ``checks`` metric: value
        ``1.0`` for pass, ``0.0`` for fail. The ``check`` tag carries the
        condition name.

        Parameters
        ----------
        value : Any
            The value to test (typically an HTTP response).
        conditions : dict[str, Callable[[Any], bool]]
            Mapping of check name to predicate function.

        Returns
        -------
        bool
            True if all conditions passed.

        >>> import queue as q
        >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
        >>> w = Worker(
        ...     sample_queue=sq,
        ...     execution=ExecutionInfo(
        ...         worker_id=1, scenario="s", iteration=0,
        ...     ),
        ... )
        >>> w.check(200, {"is 200": lambda v: v == 200})
        True
        >>> s = sq.get_nowait()
        >>> s.metric
        'checks'
        >>> s.value
        1.0
        >>> s.tags["check"]
        'is 200'
        """
        all_passed = True
        for name, predicate in conditions.items():
            try:
                passed = bool(predicate(value))
            except Exception:
                passed = False
            self._emit(
                make_sample(
                    metric="checks",
                    value=1.0 if passed else 0.0,
                    tags={
                        "check": name,
                        "scenario": self.execution.scenario,
                    },
                ),
            )
            if not passed:
                all_passed = False
        return all_passed

    def counter(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a custom counter metric sample.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Value to add (default 1.0).
        tags : dict[str, str] | None
            Optional tags.

        Examples
        --------
        >>> import queue as q
        >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
        >>> w = Worker(
        ...     sample_queue=sq,
        ...     execution=ExecutionInfo(
        ...         worker_id=1, scenario="s", iteration=0,
        ...     ),
        ... )
        >>> w.counter("my_counter", 5.0)
        >>> sq.get_nowait().value
        5.0
        """
        self._emit(make_sample(name, value, tags))

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a custom gauge metric sample.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Current value.
        tags : dict[str, str] | None
            Optional tags.

        Examples
        --------
        >>> import queue as q
        >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
        >>> w = Worker(
        ...     sample_queue=sq,
        ...     execution=ExecutionInfo(
        ...         worker_id=1, scenario="s", iteration=0,
        ...     ),
        ... )
        >>> w.gauge("queue_depth", 42.0)
        >>> sq.get_nowait().value
        42.0
        """
        self._emit(make_sample(name, value, tags))

    def trend(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a custom trend metric sample.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Observed value.
        tags : dict[str, str] | None
            Optional tags.

        Examples
        --------
        >>> import queue as q
        >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
        >>> w = Worker(
        ...     sample_queue=sq,
        ...     execution=ExecutionInfo(
        ...         worker_id=1, scenario="s", iteration=0,
        ...     ),
        ... )
        >>> w.trend("latency", 123.4)
        >>> sq.get_nowait().value
        123.4
        """
        self._emit(make_sample(name, value, tags))
