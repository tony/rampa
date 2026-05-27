"""OpenTelemetry OTLP/HTTP+JSON output.

Exports metrics to an OpenTelemetry collector via the OTLP/HTTP+JSON
protocol. Zero additional dependencies beyond aiohttp (already included).

The JSON wire format follows the proto3 standard JSON mapping defined
in the OTLP spec.

>>> import rampa.outputs.otel
"""

from __future__ import annotations

import json
import logging
import time
import typing as t

from rampa._types import Sample

logger = logging.getLogger(__name__)


def _ns_now() -> int:
    return time.time_ns()


def _samples_to_otlp(
    samples: list[Sample],
    service_name: str,
) -> dict[str, t.Any]:
    """Convert rampa samples to OTLP JSON metrics request.

    Parameters
    ----------
    samples : list[Sample]
        Batch of metric samples.
    service_name : str
        Service name for the OTLP resource.

    Returns
    -------
    dict[str, Any]
        OTLP ExportMetricsServiceRequest as JSON-compatible dict.

    >>> from rampa._types import Sample
    >>> s = Sample(metric="reqs", value=1.0, timestamp=1000, tags={})
    >>> r = _samples_to_otlp([s], "test")
    >>> len(r["resourceMetrics"])
    1
    """
    metrics_by_name: dict[str, list[dict[str, t.Any]]] = {}
    now_ns = _ns_now()

    for s in samples:
        attrs = [{"key": k, "value": {"stringValue": v}} for k, v in s.tags.items()]
        dp: dict[str, t.Any] = {
            "timeUnixNano": str(now_ns),
            "asDouble": s.value,
            "attributes": attrs,
        }
        metrics_by_name.setdefault(s.metric, []).append(dp)

    otlp_metrics: list[dict[str, t.Any]] = []
    for name, data_points in metrics_by_name.items():
        otlp_metrics.append(
            {
                "name": name,
                "gauge": {"dataPoints": data_points},
            },
        )

    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}},
                    ],
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "rampa"},
                        "metrics": otlp_metrics,
                    },
                ],
            },
        ],
    }


class OTelOutput:
    """Export metrics via OTLP/HTTP+JSON to an OpenTelemetry collector.

    Uses the JSON wire format (no protobuf dependency). Compatible with
    any OTLP-capable collector (Grafana Alloy, OTEL Collector, etc.).

    Parameters
    ----------
    url : str
        Collector endpoint. Defaults to ``http://localhost:4318``.
        The ``/v1/metrics`` path is appended automatically.
    service_name : str
        Service name in the OTLP resource.
    batch_size : int
        Flush after accumulating this many samples.

    >>> o = OTelOutput("http://localhost:4318")
    >>> o._endpoint
    'http://localhost:4318/v1/metrics'
    """

    def __init__(
        self,
        url: str = "http://localhost:4318",
        service_name: str = "rampa",
        batch_size: int = 5000,
    ) -> None:
        base = url.rstrip("/")
        self._endpoint = f"{base}/v1/metrics" if not base.endswith("/v1/metrics") else base
        self._service_name = service_name
        self._batch_size = batch_size
        self._buffer: list[Sample] = []
        self._session: t.Any = None

    async def start(self) -> None:
        """Open an aiohttp session."""
        import aiohttp

        self._session = aiohttp.ClientSession()

    async def add_samples(self, samples: list[Sample]) -> None:
        """Buffer samples and flush when batch_size is reached.

        Parameters
        ----------
        samples : list[Sample]
            Batch of samples.
        """
        self._buffer.extend(samples)
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def stop(self, error: Exception | None = None) -> None:
        """Flush remaining samples and close the session.

        Parameters
        ----------
        error : Exception | None
            The test error, if any.
        """
        if self._buffer:
            await self._flush()
        if self._session is not None:
            await self._session.close()

    async def _flush(self) -> None:
        if not self._buffer or self._session is None:
            return
        payload = _samples_to_otlp(self._buffer, self._service_name)
        self._buffer.clear()
        try:
            async with self._session.post(
                self._endpoint,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(
                        "otlp export failed: %d %s",
                        resp.status,
                        text[:200],
                    )
        except Exception:
            logger.exception("otlp export error")
