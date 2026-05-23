"""Tests for rampa output system."""

from __future__ import annotations

import asyncio
import io
import json
import typing as t

from rampa._types import Sample
from rampa.metrics import MetricSnapshot
from rampa.output import ConsoleOutput, JSONOutput, OutputManager


class _RecordingOutput:
    """Test output that records received sample batches."""

    def __init__(self) -> None:
        self.started: bool = False
        self.stopped: bool = False
        self.batches: list[list[Sample]] = []
        self.stop_error: Exception | None = None

    async def start(self) -> None:
        """Record start."""
        self.started = True

    async def add_samples(self, samples: list[Sample]) -> None:
        """Record batch."""
        self.batches.append(list(samples))

    async def stop(self, error: Exception | None = None) -> None:
        """Record stop."""
        self.stopped = True
        self.stop_error = error


def test_output_manager_fan_out() -> None:
    """OutputManager delivers the same batch to all outputs."""

    async def _run() -> tuple[_RecordingOutput, _RecordingOutput]:
        o1 = _RecordingOutput()
        o2 = _RecordingOutput()
        mgr = OutputManager()
        mgr.add(o1)
        mgr.add(o2)

        await mgr.start_all()
        mgr.buffer_sample(Sample("reqs", 1.0, 0, {}))
        mgr.buffer_sample(Sample("reqs", 1.0, 1, {}))
        await mgr.flush()
        await mgr.stop_all()
        return o1, o2

    o1, o2 = asyncio.run(_run())
    assert o1.started
    assert o2.started
    assert o1.stopped
    assert o2.stopped
    assert len(o1.batches) == 1
    assert len(o1.batches[0]) == 2
    assert len(o2.batches) == 1
    assert len(o2.batches[0]) == 2


def test_output_manager_flush_clears_buffer() -> None:
    """OutputManager clears buffer after flush."""

    async def _run() -> _RecordingOutput:
        o = _RecordingOutput()
        mgr = OutputManager()
        mgr.add(o)
        await mgr.start_all()

        mgr.buffer_sample(Sample("reqs", 1.0, 0, {}))
        await mgr.flush()
        await mgr.flush()
        await mgr.stop_all()
        return o

    o = asyncio.run(_run())
    assert len(o.batches) == 1


def test_output_manager_stop_flushes_remaining() -> None:
    """OutputManager flushes remaining samples on stop."""

    async def _run() -> _RecordingOutput:
        o = _RecordingOutput()
        mgr = OutputManager()
        mgr.add(o)
        await mgr.start_all()
        mgr.buffer_sample(Sample("reqs", 1.0, 0, {}))
        await mgr.stop_all()
        return o

    o = asyncio.run(_run())
    assert len(o.batches) == 1
    assert o.stopped


def test_console_output_renders_metrics() -> None:
    """ConsoleOutput renders metric names and values."""
    stream = io.StringIO()
    co = ConsoleOutput(stream=stream)
    snap = MetricSnapshot(
        timestamp=0,
        duration=10.0,
        values={
            "http_reqs": {"count": 100.0, "rate": 10.0},
            "http_req_duration": {
                "avg": 45.5,
                "min": 10.0,
                "max": 200.0,
                "p(95)": 180.0,
            },
        },
    )
    co.render_summary(snap)
    output = stream.getvalue()
    assert "http_reqs" in output
    assert "http_req_duration" in output
    assert "100" in output
    assert "rampa summary" in output


def test_console_output_renders_thresholds() -> None:
    """ConsoleOutput renders threshold pass/fail status."""

    class _FakeResult(t.NamedTuple):
        source: str
        passed: bool

    stream = io.StringIO()
    co = ConsoleOutput(stream=stream)
    snap = MetricSnapshot(timestamp=0, duration=5.0, values={})
    co.render_summary(
        snap,
        threshold_results=[
            _FakeResult("p(95)<500", True),
            _FakeResult("rate<0.01", False),
        ],
    )
    output = stream.getvalue()
    assert "p(95)<500" in output
    assert "rate<0.01" in output


def test_json_output_writes_samples(tmp_path: t.Any) -> None:
    """JSONOutput writes samples to a JSON file."""
    path = tmp_path / "result.json"

    async def _run() -> None:
        jo = JSONOutput(str(path))
        await jo.start()
        await jo.add_samples(
            [
                Sample("reqs", 1.0, 100, {"method": "GET"}),
                Sample("reqs", 1.0, 200, {"method": "POST"}),
            ]
        )
        await jo.stop()

    asyncio.run(_run())
    data = json.loads(path.read_text())
    assert len(data["samples"]) == 2
    assert data["samples"][0]["metric"] == "reqs"
    assert data["samples"][1]["tags"]["method"] == "POST"


def test_json_output_writes_summary(tmp_path: t.Any) -> None:
    """JSONOutput.write_summary appends summary data."""
    path = tmp_path / "result.json"

    async def _run() -> None:
        jo = JSONOutput(str(path))
        await jo.start()
        await jo.add_samples([Sample("reqs", 1.0, 0, {})])
        await jo.stop()
        jo.write_summary(
            MetricSnapshot(
                timestamp=0,
                duration=10.0,
                values={"reqs": {"count": 1.0, "rate": 0.1}},
            ),
        )

    asyncio.run(_run())
    data = json.loads(path.read_text())
    assert "summary" in data
    assert data["summary"]["duration"] == 10.0
    assert data["summary"]["metrics"]["reqs"]["count"] == 1.0
