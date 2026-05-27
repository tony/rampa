"""CSV output — writes one row per sample to a flat file.

>>> import rampa.outputs.csv
"""

from __future__ import annotations

import csv
import io
import pathlib

from rampa._types import Sample


class CSVOutput:
    """Write samples to a CSV file, one row per sample.

    Columns: ``timestamp``, ``metric``, ``value``, plus one column per
    unique tag key discovered across all samples.

    >>> co = CSVOutput("/dev/null")
    >>> str(co._path)
    '/dev/null'
    """

    def __init__(self, path: str) -> None:
        self._path = pathlib.Path(path)
        self._samples: list[Sample] = []

    async def start(self) -> None:
        """No-op — file is written at stop time."""

    async def add_samples(self, samples: list[Sample]) -> None:
        """Buffer samples for CSV serialization.

        Parameters
        ----------
        samples : list[Sample]
            Batch of samples.
        """
        self._samples.extend(samples)

    async def stop(self, error: Exception | None = None) -> None:
        """Write accumulated samples to the CSV file.

        Parameters
        ----------
        error : Exception | None
            The test error, if any.
        """
        if not self._samples:
            self._path.write_text("")
            return

        tag_keys = sorted(
            {k for s in self._samples for k in s.tags},
        )
        fieldnames = ["timestamp", "metric", "value", *tag_keys]

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for s in self._samples:
            row: dict[str, object] = {
                "timestamp": s.timestamp,
                "metric": s.metric,
                "value": s.value,
            }
            for k in tag_keys:
                row[k] = s.tags.get(k, "")
            writer.writerow(row)

        self._path.write_text(buf.getvalue())
