"""Tests for MCP resource payloads."""

from __future__ import annotations

import asyncio
import json
import typing as t

import pytest

from rampa.events import PhaseEvent
from rampa.mcp import resources
from rampa.mcp.registry import RunRecord, RunRegistry

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


JsonResource = t.Callable[..., t.Awaitable[str]]


class FakeMCP:
    """Minimal MCP resource collector for resource registration tests."""

    def __init__(self) -> None:
        self.resources: dict[str, JsonResource] = {}

    def resource(
        self,
        uri: str,
        *,
        title: str,
        mime_type: str,
    ) -> t.Callable[[JsonResource], JsonResource]:
        """Collect a registered resource callback."""
        _ = title, mime_type

        def decorator(func: JsonResource) -> JsonResource:
            self.resources[uri] = func
            return func

        return decorator


def test_run_events_resource_serializes_specific_event_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The event resource includes event-specific fields."""
    registry = RunRegistry()
    record = RunRecord(run_id="run-1", script_path="load_test.py", started_at=0.0)
    record.events.append(PhaseEvent(run_id="run-1", timestamp_ns=10, phase="setup"))
    registry.register(record)
    monkeypatch.setattr(resources, "get_registry", lambda: registry)

    mcp = FakeMCP()
    resources.register(t.cast("FastMCP", mcp))

    payload = json.loads(
        asyncio.run(mcp.resources["rampa://runs/{run_id}/events"]("run-1")),
    )

    assert payload["events"] == [
        {
            "run_id": "run-1",
            "timestamp_ns": 10,
            "phase": "setup",
            "type": "PhaseEvent",
        },
    ]
