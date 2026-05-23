"""Metric registry, sinks, and aggregation engine for rampa.

The metric engine runs in a dedicated thread, draining samples from a
``queue.SimpleQueue`` and updating per-metric sinks. It periodically emits
``MetricSnapshot`` objects for outputs and threshold evaluation.

>>> import rampa.metrics
"""

from __future__ import annotations

import math
import queue
import threading
import time
from dataclasses import dataclass, field

from rampa._types import MetricType, Sample, ValueType


@dataclass
class Metric:
    """A registered metric with name, type, and value type.

    >>> m = Metric(name="http_reqs", metric_type=MetricType.COUNTER)
    >>> m.metric_type
    <MetricType.COUNTER: 'counter'>
    """

    name: str
    metric_type: MetricType
    value_type: ValueType = ValueType.DEFAULT


class CounterSink:
    """Accumulates a running total and computes rate.

    >>> s = CounterSink()
    >>> s.add(1.0)
    >>> s.add(2.0)
    >>> s.format(10.0)
    {'count': 3.0, 'rate': 0.3}
    """

    def __init__(self) -> None:
        self._value: float = 0.0

    def add(self, value: float) -> None:
        """Add a value to the counter."""
        self._value += value

    def format(self, duration: float) -> dict[str, float]:
        """Return aggregated values.

        Parameters
        ----------
        duration : float
            Elapsed test duration in seconds.

        Returns
        -------
        dict[str, float]
            Aggregation with ``count`` and ``rate`` keys.
        """
        rate = self._value / duration if duration > 0 else 0.0
        return {"count": self._value, "rate": rate}


class GaugeSink:
    """Tracks the latest value plus min and max.

    >>> s = GaugeSink()
    >>> s.add(10.0)
    >>> s.add(5.0)
    >>> s.add(20.0)
    >>> s.format(1.0)
    {'value': 20.0, 'min': 5.0, 'max': 20.0}
    """

    def __init__(self) -> None:
        self._value: float = 0.0
        self._min: float = math.inf
        self._max: float = -math.inf

    def add(self, value: float) -> None:
        """Record a gauge observation."""
        self._value = value
        self._min = min(self._min, value)
        self._max = max(self._max, value)

    def format(self, duration: float) -> dict[str, float]:
        """Return aggregated values.

        Parameters
        ----------
        duration : float
            Elapsed test duration in seconds (unused for gauge).

        Returns
        -------
        dict[str, float]
            Aggregation with ``value``, ``min``, ``max`` keys.
        """
        return {
            "value": self._value,
            "min": self._min if self._min != math.inf else 0.0,
            "max": self._max if self._max != -math.inf else 0.0,
        }


class RateSink:
    """Tracks the fraction of non-zero (truthy) values.

    >>> s = RateSink()
    >>> s.add(1.0)
    >>> s.add(0.0)
    >>> s.add(1.0)
    >>> fmt = s.format(1.0)
    >>> fmt["passes"]
    2.0
    >>> fmt["fails"]
    1.0
    """

    def __init__(self) -> None:
        self._trues: int = 0
        self._total: int = 0

    def add(self, value: float) -> None:
        """Record a boolean observation (non-zero = true)."""
        self._total += 1
        if value != 0.0:
            self._trues += 1

    def format(self, duration: float) -> dict[str, float]:
        """Return aggregated values.

        Parameters
        ----------
        duration : float
            Elapsed test duration in seconds (unused for rate).

        Returns
        -------
        dict[str, float]
            Aggregation with ``rate``, ``passes``, ``fails`` keys.
        """
        rate = self._trues / self._total if self._total > 0 else 0.0
        return {
            "rate": rate,
            "passes": float(self._trues),
            "fails": float(self._total - self._trues),
        }


class TrendSink:
    """Stores all values for percentile computation.

    Uses linear interpolation matching NumPy's default algorithm.

    >>> s = TrendSink()
    >>> for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
    ...     s.add(v)
    >>> fmt = s.format(1.0)
    >>> fmt["min"]
    10.0
    >>> fmt["max"]
    50.0
    >>> fmt["avg"]
    30.0
    >>> fmt["med"]
    30.0
    >>> fmt["count"]
    5.0
    """

    def __init__(self) -> None:
        self._values: list[float] = []
        self._sorted: bool = False

    def add(self, value: float) -> None:
        """Record a trend observation."""
        self._values.append(value)
        self._sorted = False

    def _ensure_sorted(self) -> None:
        if not self._sorted:
            self._values.sort()
            self._sorted = True

    def percentile(self, p: float) -> float:
        """Compute a percentile using linear interpolation.

        Parameters
        ----------
        p : float
            Percentile in the range [0, 100].

        Returns
        -------
        float
            Interpolated percentile value.

        >>> s = TrendSink()
        >>> for v in range(1, 101):
        ...     s.add(float(v))
        >>> s.percentile(50)
        50.5
        >>> s.percentile(90)  # doctest: +ELLIPSIS
        90.1...
        >>> s.percentile(95)  # doctest: +ELLIPSIS
        95.0...
        >>> s.percentile(99)  # doctest: +ELLIPSIS
        99.0...
        """
        if not self._values:
            return 0.0
        self._ensure_sorted()
        n = len(self._values)
        if n == 1:
            return self._values[0]
        rank = (p / 100.0) * (n - 1)
        lower = int(rank)
        upper = lower + 1
        if upper >= n:
            return self._values[-1]
        frac = rank - lower
        return self._values[lower] + frac * (self._values[upper] - self._values[lower])

    def format(self, duration: float) -> dict[str, float]:
        """Return aggregated values.

        Parameters
        ----------
        duration : float
            Elapsed test duration in seconds (unused for trend).

        Returns
        -------
        dict[str, float]
            Aggregation with stat keys.
        """
        if not self._values:
            return {
                "count": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "med": 0.0,
                "p(90)": 0.0,
                "p(95)": 0.0,
                "p(99)": 0.0,
            }
        self._ensure_sorted()
        total = sum(self._values)
        count = len(self._values)
        return {
            "count": float(count),
            "avg": total / count,
            "min": self._values[0],
            "max": self._values[-1],
            "med": self.percentile(50),
            "p(90)": self.percentile(90),
            "p(95)": self.percentile(95),
            "p(99)": self.percentile(99),
        }


Sink = CounterSink | GaugeSink | RateSink | TrendSink
"""Union type for all metric sink implementations."""


def create_sink(metric_type: MetricType) -> Sink:
    """Create a sink matching the metric type.

    Parameters
    ----------
    metric_type : MetricType
        The type of metric.

    Returns
    -------
    Sink
        A new sink instance.

    >>> type(create_sink(MetricType.COUNTER)).__name__
    'CounterSink'
    >>> type(create_sink(MetricType.TREND)).__name__
    'TrendSink'
    """
    match metric_type:
        case MetricType.COUNTER:
            return CounterSink()
        case MetricType.GAUGE:
            return GaugeSink()
        case MetricType.RATE:
            return RateSink()
        case MetricType.TREND:
            return TrendSink()


class MetricRegistry:
    """Thread-safe registry that enforces name-type consistency.

    >>> reg = MetricRegistry()
    >>> reg.get_or_create("reqs", MetricType.COUNTER).metric_type
    <MetricType.COUNTER: 'counter'>
    >>> reg.get_or_create("reqs", MetricType.COUNTER).name
    'reqs'
    """

    def __init__(self) -> None:
        self._metrics: dict[str, Metric] = {}
        self._sinks: dict[str, Sink] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        name: str,
        metric_type: MetricType,
        value_type: ValueType = ValueType.DEFAULT,
    ) -> Metric:
        """Register or retrieve a metric by name.

        Parameters
        ----------
        name : str
            Metric name.
        metric_type : MetricType
            Expected metric type.
        value_type : ValueType
            Value type hint for display.

        Returns
        -------
        Metric
            The registered metric.

        Raises
        ------
        ValueError
            If the name is already registered with a different type.
        """
        with self._lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if existing.metric_type != metric_type:
                    msg = (
                        f"metric {name!r} already registered as "
                        f"{existing.metric_type.value}, "
                        f"cannot re-register as {metric_type.value}"
                    )
                    raise ValueError(msg)
                return existing
            metric = Metric(
                name=name,
                metric_type=metric_type,
                value_type=value_type,
            )
            self._metrics[name] = metric
            self._sinks[name] = create_sink(metric_type)
            return metric

    def get_sink(self, name: str) -> Sink | None:
        """Return the sink for a metric, or None if not registered."""
        return self._sinks.get(name)

    def all_metrics(self) -> dict[str, Metric]:
        """Return a snapshot of all registered metrics."""
        with self._lock:
            return dict(self._metrics)

    def all_sinks(self) -> dict[str, Sink]:
        """Return a snapshot of all sinks."""
        with self._lock:
            return dict(self._sinks)


@dataclass(frozen=True)
class MetricSnapshot:
    """Frozen snapshot of aggregated metric values at a point in time.

    >>> snap = MetricSnapshot(
    ...     timestamp=0,
    ...     duration=10.0,
    ...     values={"reqs": {"count": 100.0, "rate": 10.0}},
    ... )
    >>> snap.values["reqs"]["rate"]
    10.0
    """

    timestamp: int
    duration: float
    values: dict[str, dict[str, float]]


_BUILTIN_METRICS: list[tuple[str, MetricType, ValueType]] = [
    ("iterations", MetricType.COUNTER, ValueType.DEFAULT),
    ("iteration_duration", MetricType.TREND, ValueType.TIME),
    ("dropped_iterations", MetricType.COUNTER, ValueType.DEFAULT),
    ("vus", MetricType.GAUGE, ValueType.DEFAULT),
    ("vus_max", MetricType.GAUGE, ValueType.DEFAULT),
    ("checks", MetricType.RATE, ValueType.DEFAULT),
    ("data_sent", MetricType.COUNTER, ValueType.DATA),
    ("data_received", MetricType.COUNTER, ValueType.DATA),
]


def register_builtins(registry: MetricRegistry) -> None:
    """Register all built-in metrics.

    Parameters
    ----------
    registry : MetricRegistry
        The registry to populate.

    >>> reg = MetricRegistry()
    >>> register_builtins(reg)
    >>> reg.get_sink("iterations") is not None
    True
    >>> reg.get_sink("checks") is not None
    True
    """
    for name, metric_type, value_type in _BUILTIN_METRICS:
        registry.get_or_create(name, metric_type, value_type)


@dataclass
class MetricEngine:
    """Background thread that drains samples and updates sinks.

    Parameters
    ----------
    registry : MetricRegistry
        Metric registry with sinks.
    sample_queue : queue.SimpleQueue[Sample | None]
        Queue of samples. Send ``None`` to signal shutdown.
    flush_interval : float
        Seconds between snapshot emissions.

    >>> eng = MetricEngine(
    ...     registry=MetricRegistry(),
    ...     sample_queue=queue.SimpleQueue(),
    ... )
    >>> eng.flush_interval
    0.05
    """

    registry: MetricRegistry
    sample_queue: queue.SimpleQueue[Sample | None]
    flush_interval: float = 0.05
    _thread: threading.Thread = field(init=False, repr=False)
    _running: bool = field(init=False, default=False, repr=False)
    _start_time: float = field(init=False, default=0.0, repr=False)
    _snapshots: list[MetricSnapshot] = field(
        init=False,
        default_factory=list,
        repr=False,
    )
    _snapshot_lock: threading.Lock = field(
        init=False,
        default_factory=threading.Lock,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Initialize the background thread."""
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="rampa-metric-engine",
        )

    def start(self) -> None:
        """Start the background aggregation thread."""
        self._running = True
        self._start_time = time.monotonic()
        self._thread.start()

    def stop(self) -> None:
        """Signal shutdown and wait for the thread to finish."""
        self._running = False
        self.sample_queue.put(None)
        self._thread.join(timeout=5.0)

    def get_latest_snapshot(self) -> MetricSnapshot | None:
        """Return the most recent snapshot, or None if none emitted yet."""
        with self._snapshot_lock:
            return self._snapshots[-1] if self._snapshots else None

    def _run(self) -> None:
        last_flush = time.monotonic()
        while self._running:
            try:
                sample = self.sample_queue.get(timeout=self.flush_interval)
            except Exception:
                sample = None

            if sample is not None:
                self._ingest(sample)

            now = time.monotonic()
            if now - last_flush >= self.flush_interval:
                self._emit_snapshot()
                last_flush = now

        self._drain_remaining()
        self._emit_snapshot()

    def _drain_remaining(self) -> None:
        while True:
            try:
                sample = self.sample_queue.get_nowait()
            except Exception:
                break
            if sample is not None:
                self._ingest(sample)

    def _ingest(self, sample: Sample) -> None:
        sink = self.registry.get_sink(sample.metric)
        if sink is None:
            self.registry.get_or_create(
                sample.metric,
                MetricType.TREND,
            )
            sink = self.registry.get_sink(sample.metric)
        if sink is not None:
            sink.add(sample.value)

    def _emit_snapshot(self) -> None:
        elapsed = time.monotonic() - self._start_time
        sinks = self.registry.all_sinks()
        values: dict[str, dict[str, float]] = {}
        for name, sink in sinks.items():
            values[name] = sink.format(elapsed)
        snapshot = MetricSnapshot(
            timestamp=time.monotonic_ns(),
            duration=elapsed,
            values=values,
        )
        with self._snapshot_lock:
            self._snapshots.append(snapshot)
