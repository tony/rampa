"""Output protocol, manager, and built-in outputs for rampa.

Outputs consume metric sample batches asynchronously. The OutputManager fans
out each batch to all registered outputs on a periodic timer. Outputs never
reach into executor or worker internals.

>>> import rampa.output
"""

from __future__ import annotations

import json
import pathlib
import sys
import typing as t
from dataclasses import dataclass, field

from rampa._types import Sample
from rampa.metrics import MetricSnapshot


class Output(t.Protocol):
    """Protocol for metric output backends.

    Outputs receive batched samples on a periodic flush interval. They must
    not block the engine's sample fan-out path.
    """

    async def start(self) -> None:
        """Initialize the output (open files, connections, etc.)."""
        ...

    async def add_samples(self, samples: list[Sample]) -> None:
        """Receive a batch of samples.

        Parameters
        ----------
        samples : list[Sample]
            Batch of metric samples to process.
        """
        ...

    async def stop(self, error: Exception | None = None) -> None:
        """Finalize the output (flush, close files, etc.).

        Parameters
        ----------
        error : Exception | None
            The test error, if any, that caused the run to end.
        """
        ...


@dataclass
class OutputManager:
    """Fans out sample batches to all registered outputs.

    >>> import asyncio
    >>> mgr = OutputManager()
    >>> len(mgr.outputs)
    0
    """

    outputs: list[Output] = field(default_factory=list)
    _samples: list[Sample] = field(default_factory=list, repr=False)

    def add(self, output: Output) -> None:
        """Register an output backend.

        Parameters
        ----------
        output : Output
            Output to add.
        """
        self.outputs.append(output)

    def buffer_sample(self, sample: Sample) -> None:
        """Buffer a sample for the next flush.

        Parameters
        ----------
        sample : Sample
            Sample to buffer.
        """
        self._samples.append(sample)

    def buffer_samples(self, samples: list[Sample]) -> None:
        """Buffer multiple samples for the next flush.

        Parameters
        ----------
        samples : list[Sample]
            Samples to buffer.
        """
        self._samples.extend(samples)

    async def start_all(self) -> None:
        """Start all registered outputs."""
        for output in self.outputs:
            await output.start()

    async def flush(self) -> None:
        """Flush buffered samples to all outputs."""
        if not self._samples:
            return
        batch = self._samples
        self._samples = []
        for output in self.outputs:
            await output.add_samples(batch)

    async def stop_all(self, error: Exception | None = None) -> None:
        """Flush remaining samples and stop all outputs.

        Parameters
        ----------
        error : Exception | None
            The test error, if any.
        """
        await self.flush()
        for output in self.outputs:
            await output.stop(error)


class ConsoleOutput:
    """Renders an end-of-test summary to a text stream.

    >>> co = ConsoleOutput()
    >>> co._stream is sys.stdout
    True
    """

    def __init__(self, stream: t.TextIO | None = None) -> None:
        self._stream: t.TextIO = stream or sys.stdout
        self._snapshot: MetricSnapshot | None = None

    async def start(self) -> None:
        """No-op for console output."""

    async def add_samples(self, samples: list[Sample]) -> None:
        """No-op — console renders from the final snapshot, not samples."""

    async def stop(self, error: Exception | None = None) -> None:
        """No-op — rendering happens via render_summary."""

    def render_summary(
        self,
        snapshot: MetricSnapshot,
        threshold_results: list[t.Any] | None = None,
    ) -> None:
        """Render a human-readable summary to the stream.

        Parameters
        ----------
        snapshot : MetricSnapshot
            Final metric aggregation snapshot.
        threshold_results : list[Any] | None
            Threshold evaluation results.

        >>> import io
        >>> from rampa.metrics import MetricSnapshot
        >>> stream = io.StringIO()
        >>> co = ConsoleOutput(stream=stream)
        >>> snap = MetricSnapshot(
        ...     timestamp=0,
        ...     duration=10.0,
        ...     values={"http_reqs": {"count": 100.0, "rate": 10.0}},
        ... )
        >>> co.render_summary(snap)
        >>> "http_reqs" in stream.getvalue()
        True
        """
        w = self._stream.write

        w("\n")
        w("=" * 60 + "\n")
        w(f"  rampa summary (duration: {snapshot.duration:.1f}s)\n")
        w("=" * 60 + "\n\n")

        if threshold_results:
            w("  thresholds:\n")
            for result in threshold_results:
                status = "✓" if result.passed else "✗"
                w(f"    {status} {result.source}\n")
            w("\n")

        for metric_name, values in sorted(snapshot.values.items()):
            w(f"  {metric_name}:\n")
            for key, val in values.items():
                if isinstance(val, float) and val == int(val) and val < 1e15:
                    w(f"    {key}: {int(val)}\n")
                elif isinstance(val, float):
                    w(f"    {key}: {val:.4f}\n")
                else:
                    w(f"    {key}: {val}\n")
            w("\n")


class JSONOutput:
    """Writes samples and summary to a JSON file.

    >>> jo = JSONOutput("/dev/null")
    >>> str(jo._path)
    '/dev/null'
    """

    def __init__(self, path: str) -> None:
        self._path = pathlib.Path(path)
        self._samples: list[dict[str, t.Any]] = []

    async def start(self) -> None:
        """No-op — file is written at stop time."""

    async def add_samples(self, samples: list[Sample]) -> None:
        """Buffer samples for JSON serialization.

        Parameters
        ----------
        samples : list[Sample]
            Batch of samples.
        """
        for s in samples:
            self._samples.append(
                {
                    "metric": s.metric,
                    "value": s.value,
                    "timestamp": s.timestamp,
                    "tags": s.tags,
                }
            )

    async def stop(self, error: Exception | None = None) -> None:
        """Write accumulated samples to the JSON file.

        Parameters
        ----------
        error : Exception | None
            The test error, if any.
        """
        data = {"samples": self._samples}
        with self._path.open("w") as f:
            json.dump(data, f, indent=2)

    def write_summary(
        self,
        snapshot: MetricSnapshot,
        threshold_results: list[t.Any] | None = None,
    ) -> None:
        """Append summary data to the JSON output file.

        Parameters
        ----------
        snapshot : MetricSnapshot
            Final metric aggregation snapshot.
        threshold_results : list[Any] | None
            Threshold evaluation results.
        """
        try:
            with self._path.open() as f:
                data = json.load(f)
        except FileNotFoundError, json.JSONDecodeError:
            data = {}

        data["summary"] = {
            "duration": snapshot.duration,
            "metrics": snapshot.values,
        }
        if threshold_results:
            data["thresholds"] = [
                {
                    "source": r.source,
                    "passed": r.passed,
                    "lhs": r.lhs,
                    "rhs": r.rhs,
                }
                for r in threshold_results
            ]

        with self._path.open("w") as f:
            json.dump(data, f, indent=2)
