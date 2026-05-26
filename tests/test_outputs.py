"""Tests for rampa output backends."""

from __future__ import annotations

import asyncio
import pathlib
import typing as t

from rampa._types import Sample
from rampa.outputs import OUTPUT_REGISTRY, get_output
from rampa.outputs.csv import CSVOutput
from rampa.outputs.influxdb import _sample_to_line


def test_output_registry_has_all_backends() -> None:
    """All built-in backends are registered."""
    assert "console" in OUTPUT_REGISTRY
    assert "json" in OUTPUT_REGISTRY
    assert "csv" in OUTPUT_REGISTRY
    assert "influxdb" in OUTPUT_REGISTRY
    assert "webhook" in OUTPUT_REGISTRY


def test_get_output_resolves_json() -> None:
    """get_output() returns a JSONOutput for 'json'."""
    out = get_output("json", "/dev/null")
    assert type(out).__name__ == "JSONOutput"


def test_get_output_rejects_unknown() -> None:
    """get_output() raises ValueError for unknown backends."""
    import pytest

    with pytest.raises(ValueError, match="unknown output backend"):
        get_output("bogus")


def test_csv_output_writes_samples(tmp_path: t.Any) -> None:
    """CSVOutput writes a valid CSV file with tag columns."""
    path = str(tmp_path / "out.csv")
    samples = [
        Sample(
            metric="http_reqs",
            value=1.0,
            timestamp=1000,
            tags={"method": "GET", "status": "200"},
        ),
        Sample(
            metric="http_req_duration",
            value=45.2,
            timestamp=2000,
            tags={"method": "POST"},
        ),
    ]

    async def _run() -> str:
        out = CSVOutput(path)
        await out.start()
        await out.add_samples(samples)
        await out.stop()
        with pathlib.Path(path).open() as f:
            return f.read()

    text = asyncio.run(_run())
    lines = text.strip().split("\n")
    assert len(lines) == 3
    header = lines[0]
    assert "timestamp" in header
    assert "metric" in header
    assert "value" in header
    assert "method" in header
    assert "status" in header


def test_csv_output_empty_produces_empty_file(tmp_path: t.Any) -> None:
    """CSVOutput with no samples produces an empty file."""
    path = str(tmp_path / "empty.csv")

    async def _run() -> str:
        out = CSVOutput(path)
        await out.start()
        await out.stop()
        with pathlib.Path(path).open() as f:
            return f.read()

    assert asyncio.run(_run()) == ""


def test_influxdb_line_protocol_no_tags() -> None:
    """InfluxDB line protocol without tags."""
    s = Sample(metric="reqs", value=1.0, timestamp=1000000000, tags={})
    assert _sample_to_line(s) == "reqs value=1.0 1000000000"


def test_influxdb_line_protocol_with_tags() -> None:
    """InfluxDB line protocol with sorted tags."""
    s = Sample(
        metric="dur",
        value=45.2,
        timestamp=2000000000,
        tags={"status": "200", "method": "GET"},
    )
    line = _sample_to_line(s)
    assert line == "dur,method=GET,status=200 value=45.2 2000000000"
