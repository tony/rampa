"""Console output — renders an end-of-test summary to a text stream.

>>> co = ConsoleOutput()
>>> co._stream is __import__("sys").stdout
True
"""

from __future__ import annotations

import sys
import typing as t

from rampa._types import Sample
from rampa.metrics import MetricSnapshot


class ConsoleOutput:
    """Renders an end-of-test summary to a text stream.

    >>> import io
    >>> co = ConsoleOutput(stream=io.StringIO())
    >>> co._stream is not sys.stdout
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
