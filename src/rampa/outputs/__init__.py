"""Output backend registry and convenience re-exports.

All output backends implement the :class:`~rampa.output.Output` protocol
and register themselves in :data:`OUTPUT_REGISTRY` for CLI ``--output``
flag resolution.

>>> import rampa.outputs
>>> "console" in OUTPUT_REGISTRY
True
>>> "json" in OUTPUT_REGISTRY
True
>>> "csv" in OUTPUT_REGISTRY
True
>>> "influxdb" in OUTPUT_REGISTRY
True
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from rampa.output import Output

from rampa.outputs.console import ConsoleOutput
from rampa.outputs.csv import CSVOutput
from rampa.outputs.influxdb import InfluxDBOutput
from rampa.outputs.json import JSONOutput
from rampa.outputs.webhook import WebhookOutput

OUTPUT_REGISTRY: dict[str, type[Output]] = {
    "console": ConsoleOutput,  # type: ignore[dict-item]
    "json": JSONOutput,  # type: ignore[dict-item]
    "csv": CSVOutput,  # type: ignore[dict-item]
    "influxdb": InfluxDBOutput,  # type: ignore[dict-item]
    "webhook": WebhookOutput,  # type: ignore[dict-item]
}


def get_output(name: str, destination: str = "") -> Output:
    """Resolve an output backend by name.

    Parameters
    ----------
    name : str
        Backend name (e.g. ``"json"``, ``"csv"``).
    destination : str
        Backend-specific destination (file path, URL, etc.).

    Returns
    -------
    Output
        An output instance.

    Raises
    ------
    ValueError
        If the backend name is not registered.

    >>> type(get_output("json", "/dev/null")).__name__
    'JSONOutput'
    """
    cls = OUTPUT_REGISTRY.get(name)
    if cls is None:
        available = sorted(OUTPUT_REGISTRY)
        msg = f"unknown output backend: {name!r}. available: {available}"
        raise ValueError(msg)
    if name == "console":
        return cls()  # type: ignore[call-arg]
    return cls(destination)  # type: ignore[call-arg]


__all__ = [
    "OUTPUT_REGISTRY",
    "CSVOutput",
    "ConsoleOutput",
    "InfluxDBOutput",
    "JSONOutput",
    "WebhookOutput",
    "get_output",
]
