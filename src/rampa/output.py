"""Output protocol, manager, and built-in output re-exports.

Outputs consume metric sample batches asynchronously. The OutputManager fans
out each batch to all registered outputs on a periodic timer. Outputs never
reach into executor or worker internals.

Built-in output backends live in :mod:`rampa.outputs` and are re-exported
here for backwards compatibility.

>>> import rampa.output
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

from rampa._types import Sample
from rampa.outputs.console import ConsoleOutput
from rampa.outputs.json import JSONOutput


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


__all__ = [
    "ConsoleOutput",
    "JSONOutput",
    "Output",
    "OutputManager",
]
