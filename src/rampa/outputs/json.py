"""JSON output — writes samples and summary to a JSON file.

>>> jo = JSONOutput("/dev/null")
>>> str(jo._path)
'/dev/null'
"""

from __future__ import annotations

import json
import pathlib
import typing as t

from rampa._types import Sample
from rampa.metrics import MetricSnapshot


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
        _load_errors = (FileNotFoundError, json.JSONDecodeError)
        try:
            with self._path.open() as f:
                data = json.load(f)
        except _load_errors:
            data: dict[str, t.Any] = {}

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
