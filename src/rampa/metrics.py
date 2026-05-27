"""Metric registry, sinks, and aggregation engine for rampa.

The metric engine runs in a dedicated thread, draining samples from a
``queue.SimpleQueue`` and updating per-metric sinks. It periodically emits
``MetricSnapshot`` objects for outputs and threshold evaluation.

>>> import rampa.metrics
"""

from __future__ import annotations

import collections
import logging
import math
import queue
import threading
import time
import typing as t
from dataclasses import dataclass, field

from rampa._types import MetricType, Sample, ValueType

logger = logging.getLogger(__name__)


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


class SinkProtocol(t.Protocol):
    """Structural protocol for metric sink implementations.

    Enables future Rust PyO3 sinks to satisfy the interface without
    appearing in a union type.

    >>> class DummySink:
    ...     def add(self, value: float) -> None: ...
    ...     def format(self, duration: float) -> dict[str, float]:
    ...         return {}
    >>> hasattr(DummySink, "add") and hasattr(DummySink, "format")
    True
    """

    def add(self, value: float) -> None:
        """Record an observation."""
        ...

    def format(self, duration: float) -> dict[str, float]:
        """Return aggregated values."""
        ...


Sink = SinkProtocol
"""Type alias for metric sink implementations."""


class HdrTrendSink:
    """Trend sink backed by a Rust HDR histogram.

    Fixed ~20KB memory regardless of sample count. O(1) insert, O(1)
    percentile queries. Requires the ``rampa._core`` Rust extension.

    Values are stored as integer microseconds internally. The ``add()``
    method accepts float milliseconds (matching the Python TrendSink
    interface) and converts automatically.

    >>> try:
    ...     from rampa._core import HdrHistogram
    ...     s = HdrTrendSink()
    ...     for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
    ...         s.add(v)
    ...     fmt = s.format(1.0)
    ...     fmt["count"]
    ... except ImportError:
    ...     5.0
    5.0
    """

    def __init__(self) -> None:
        from rampa._core import HdrHistogram

        self._hdr = HdrHistogram(3)

    def add(self, value: float) -> None:
        """Record a trend observation (value in milliseconds)."""
        self._hdr.record(max(0, int(value * 1000)))

    def format(self, duration: float) -> dict[str, float]:
        """Return aggregated values.

        Parameters
        ----------
        duration : float
            Elapsed test duration in seconds (unused for trend).

        Returns
        -------
        dict[str, float]
            Aggregation with stat keys, values converted back to ms.
        """
        count, avg, mn, mx, med, p90, p95, p99 = self._hdr.format_stats()
        if count == 0:
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
        return {
            "count": float(count),
            "avg": avg / 1000.0,
            "min": mn / 1000.0,
            "max": mx / 1000.0,
            "med": med / 1000.0,
            "p(90)": p90 / 1000.0,
            "p(95)": p95 / 1000.0,
            "p(99)": p99 / 1000.0,
        }


_HAVE_HDR_HISTOGRAM: bool = False
try:
    from rampa._core import HdrHistogram as _HdrHistogram  # noqa: F401

    _HAVE_HDR_HISTOGRAM = True
except ImportError:
    pass

_HAVE_RUST_METRIC_CORE: bool = False
try:
    from rampa._core import MetricCore as _MetricCore  # noqa: F401

    _HAVE_RUST_METRIC_CORE = True
except ImportError:
    pass


def create_sink(metric_type: MetricType) -> Sink:
    """Create a sink matching the metric type.

    Uses Rust HDR histogram for trend sinks when available,
    falling back to the Python TrendSink.

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
    >>> type(create_sink(MetricType.TREND)).__name__ in ('TrendSink', 'HdrTrendSink')
    True
    """
    match metric_type:
        case MetricType.COUNTER:
            return CounterSink()
        case MetricType.GAUGE:
            return GaugeSink()
        case MetricType.RATE:
            return RateSink()
        case MetricType.TREND:
            if _HAVE_HDR_HISTOGRAM:
                return HdrTrendSink()  # type: ignore[return-value]
            return TrendSink()


SubmetricKey = tuple[str, frozenset[tuple[str, str]]]
"""Identifies a tag-filtered view of a base metric.

The first element is the base metric name, the second is a frozen
set of (tag_key, tag_value) pairs used for matching.
"""


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
        self._sub_sinks: dict[SubmetricKey, Sink] = {}
        self._sub_sinks_by_metric: dict[str, list[tuple[frozenset[tuple[str, str]], Sink]]] = {}
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
        """Return a snapshot of all base sinks."""
        with self._lock:
            return dict(self._sinks)

    def get_or_create_sub_sink(
        self,
        base_name: str,
        tag_filter: dict[str, str],
    ) -> Sink | None:
        """Get or create a sub-sink for tag-filtered threshold evaluation.

        Parameters
        ----------
        base_name : str
            Base metric name.
        tag_filter : dict[str, str]
            Tags that samples must match to feed this sub-sink.

        Returns
        -------
        Sink | None
            The sub-sink, or None if the base metric is not registered.

        >>> reg = MetricRegistry()
        >>> _ = reg.get_or_create("dur", MetricType.TREND)
        >>> sink = reg.get_or_create_sub_sink("dur", {"status": "200"})
        >>> type(sink).__name__ in ('TrendSink', 'HdrTrendSink')
        True
        """
        with self._lock:
            metric = self._metrics.get(base_name)
            if metric is None:
                return None
            key: SubmetricKey = (base_name, frozenset(tag_filter.items()))
            if key not in self._sub_sinks:
                sink = create_sink(metric.metric_type)
                self._sub_sinks[key] = sink
                self._sub_sinks_by_metric.setdefault(base_name, []).append(
                    (key[1], sink),
                )
            return self._sub_sinks[key]

    def get_sub_sink(self, key: SubmetricKey) -> Sink | None:
        """Return a sub-sink by key, or None if not registered."""
        return self._sub_sinks.get(key)

    def sub_sinks_for(
        self,
        base_name: str,
    ) -> list[tuple[frozenset[tuple[str, str]], Sink]]:
        """Return sub-sinks for a specific base metric name.

        Parameters
        ----------
        base_name : str
            Base metric name to look up.

        Returns
        -------
        list[tuple[frozenset[tuple[str, str]], Sink]]
            List of ``(tag_filter, sink)`` pairs for the given metric.

        >>> reg = MetricRegistry()
        >>> _ = reg.get_or_create("dur", MetricType.TREND)
        >>> _ = reg.get_or_create_sub_sink("dur", {"status": "200"})
        >>> len(reg.sub_sinks_for("dur"))
        1
        >>> len(reg.sub_sinks_for("missing"))
        0
        """
        with self._lock:
            return list(self._sub_sinks_by_metric.get(base_name, []))

    def all_sub_sinks(self) -> dict[SubmetricKey, Sink]:
        """Return a snapshot of all sub-sinks."""
        with self._lock:
            return dict(self._sub_sinks)

    def all_sub_sinks_by_metric(
        self,
    ) -> dict[str, list[tuple[frozenset[tuple[str, str]], Sink]]]:
        """Return all sub-sinks indexed by base metric name.

        Returns
        -------
        dict[str, list[tuple[frozenset[tuple[str, str]], Sink]]]
            Mapping from base metric name to list of ``(tag_filter, sink)`` pairs.

        >>> reg = MetricRegistry()
        >>> _ = reg.get_or_create("dur", MetricType.TREND)
        >>> _ = reg.get_or_create_sub_sink("dur", {"status": "200"})
        >>> by_metric = reg.all_sub_sinks_by_metric()
        >>> "dur" in by_metric
        True
        """
        with self._lock:
            return {k: list(v) for k, v in self._sub_sinks_by_metric.items()}


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
    ("iteration_errors", MetricType.COUNTER, ValueType.DEFAULT),
    ("dropped_iterations", MetricType.COUNTER, ValueType.DEFAULT),
    ("vus", MetricType.GAUGE, ValueType.DEFAULT),
    ("vus_max", MetricType.GAUGE, ValueType.DEFAULT),
    ("checks", MetricType.RATE, ValueType.DEFAULT),
    ("data_sent", MetricType.COUNTER, ValueType.DATA),
    ("data_received", MetricType.COUNTER, ValueType.DATA),
    ("http_reqs", MetricType.COUNTER, ValueType.DEFAULT),
    ("http_req_duration", MetricType.TREND, ValueType.TIME),
    ("http_req_failed", MetricType.RATE, ValueType.DEFAULT),
    ("http_req_blocked", MetricType.TREND, ValueType.TIME),
    ("http_req_connecting", MetricType.TREND, ValueType.TIME),
    ("http_req_sending", MetricType.TREND, ValueType.TIME),
    ("http_req_waiting", MetricType.TREND, ValueType.TIME),
    ("http_req_receiving", MetricType.TREND, ValueType.TIME),
    ("ws_sessions", MetricType.COUNTER, ValueType.DEFAULT),
    ("ws_connecting", MetricType.TREND, ValueType.TIME),
    ("ws_session_duration", MetricType.TREND, ValueType.TIME),
    ("ws_messages_sent", MetricType.COUNTER, ValueType.DEFAULT),
    ("ws_messages_received", MetricType.COUNTER, ValueType.DEFAULT),
    ("ws_errors", MetricType.COUNTER, ValueType.DEFAULT),
    ("grpc_reqs", MetricType.COUNTER, ValueType.DEFAULT),
    ("grpc_req_duration", MetricType.TREND, ValueType.TIME),
    ("grpc_req_failed", MetricType.RATE, ValueType.DEFAULT),
    ("grpc_streams_opened", MetricType.COUNTER, ValueType.DEFAULT),
    ("grpc_messages_sent", MetricType.COUNTER, ValueType.DEFAULT),
    ("grpc_messages_received", MetricType.COUNTER, ValueType.DEFAULT),
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

    Examples
    --------
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
    on_sample: t.Callable[[Sample], None] | None = None
    on_snapshot: t.Callable[[MetricSnapshot], None] | None = None
    thresholds: dict[str, list[t.Any]] = field(default_factory=dict)
    threshold_interval: float = 2.0
    on_threshold: t.Callable[[list[t.Any]], None] | None = None
    abort_callback: t.Callable[[], None] | None = None
    _thread: threading.Thread = field(init=False, repr=False)
    _running: bool = field(init=False, default=False, repr=False)
    _start_time: float = field(init=False, default=0.0, repr=False)
    _last_threshold_check: float = field(
        init=False,
        default=0.0,
        repr=False,
    )
    _grace_deadlines: dict[str, float] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )
    _snapshots: collections.deque[MetricSnapshot] = field(
        init=False,
        repr=False,
    )
    _snapshot_lock: threading.Lock = field(
        init=False,
        default_factory=threading.Lock,
        repr=False,
    )

    _cached_sub_sinks: dict[t.Any, t.Any] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )

    _cached_sub_sinks_by_metric: dict[str, list[tuple[frozenset[tuple[str, str]], Sink]]] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Initialize the background thread and bounded snapshot storage."""
        self._snapshots = collections.deque(maxlen=128)
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="rampa-metric-engine",
        )

    def start(self) -> None:
        """Start the background aggregation thread."""
        self._running = True
        self._start_time = time.monotonic()
        self._cached_sub_sinks = self.registry.all_sub_sinks()
        self._cached_sub_sinks_by_metric = self.registry.all_sub_sinks_by_metric()
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
            except queue.Empty:
                sample = None

            if sample is not None:
                self._ingest(sample)
                self._drain_available()

            now = time.monotonic()
            if now - last_flush >= self.flush_interval:
                self._emit_snapshot()
                last_flush = now

        self._drain_available(limit=None)
        self._emit_snapshot()

    def _drain_available(self, limit: int | None = 10_000) -> int:
        """Drain available samples without blocking.

        Parameters
        ----------
        limit : int | None
            Maximum samples to drain per call. ``None`` drains until
            the queue is empty (used during shutdown).

        Returns
        -------
        int
            Number of samples ingested.
        """
        count = 0
        while limit is None or count < limit:
            try:
                sample = self.sample_queue.get_nowait()
            except queue.Empty:
                break
            if sample is None:
                break
            self._ingest(sample)
            count += 1
        return count

    def _ingest(self, sample: Sample) -> None:
        if self.on_sample is not None:
            self.on_sample(sample)
        sink = self.registry.get_sink(sample.metric)
        if sink is None:
            self.registry.get_or_create(
                sample.metric,
                MetricType.TREND,
            )
            sink = self.registry.get_sink(sample.metric)
        if sink is not None:
            sink.add(sample.value)

        for tag_set, sub_sink in self._cached_sub_sinks_by_metric.get(sample.metric, ()):
            if all(sample.tags.get(k) == v for k, v in tag_set):
                sub_sink.add(sample.value)

    def _emit_snapshot(self) -> None:
        elapsed = time.monotonic() - self._start_time
        self._cached_sub_sinks = self.registry.all_sub_sinks()
        self._cached_sub_sinks_by_metric = self.registry.all_sub_sinks_by_metric()
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
        if self.on_snapshot is not None:
            self.on_snapshot(snapshot)

        now = time.monotonic()
        if self.thresholds and now - self._last_threshold_check >= self.threshold_interval:
            self._last_threshold_check = now
            self._check_thresholds(snapshot, elapsed)

    def _check_thresholds(
        self,
        snapshot: MetricSnapshot,
        elapsed: float,
    ) -> None:
        from rampa.thresholds import evaluate_thresholds

        results = evaluate_thresholds(
            self.thresholds,
            self.registry.all_sinks(),
            elapsed,
            sub_sinks=self.registry.all_sub_sinks(),
        )

        if self.on_threshold is not None:
            self.on_threshold(results)

        for result in results:
            if result.passed:
                self._grace_deadlines.pop(result.source, None)
                continue

            threshold = self._find_threshold(result.source)
            if threshold is None or not threshold.abort_on_fail:
                continue

            now = time.monotonic()
            if threshold.grace_period is not None and threshold.grace_period > 0:
                if result.source not in self._grace_deadlines:
                    self._grace_deadlines[result.source] = now + threshold.grace_period
                    continue
                if now < self._grace_deadlines[result.source]:
                    continue

            if self.abort_callback is not None:
                logger.warning(
                    "threshold abort: %s",
                    result.source,
                )
                self.abort_callback()
                return

    def _find_threshold(self, source: str) -> t.Any | None:
        if self.thresholds is None:
            return None
        for thresholds in self.thresholds.values():
            for threshold in thresholds:
                if threshold.source == source:
                    return threshold
        return None
