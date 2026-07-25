"""Tests for rampa's warning policy.

The suite runs under ``filterwarnings = ["error"]`` so that upstream
deprecations and rampa's own resource leaks fail the build instead of
scrolling past. These tests guard that the policy is in force and that
there is something for it to catch.
"""

from __future__ import annotations

import asyncio
import gc
import queue
import warnings

import pytest

from rampa._types import Sample
from rampa.http import HttpClient


def test_warning_policy_is_fatal(pytestconfig: pytest.Config) -> None:
    """Warnings are configured to fail the suite."""
    assert "error" in pytestconfig.getini("filterwarnings")


def test_unclosed_session_is_detectable() -> None:
    """Dropping an HttpClient without close() reports an unclosed session.

    Collection is explicit because the client and its trace config form a
    reference cycle: the trace callbacks close over the client that owns
    them, so nothing is released until a cyclic pass runs.
    """
    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()

    async def _leak() -> HttpClient:
        client = HttpClient(sq, {})
        await client._ensure_session()
        return client

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = asyncio.run(_leak())
        del client
        gc.collect()

    leaks = [
        str(w.message)
        for w in caught
        if issubclass(w.category, ResourceWarning) and "Unclosed client session" in str(w.message)
    ]
    assert leaks, [str(w.message) for w in caught]


def test_closed_session_is_silent() -> None:
    """A closed HttpClient reports no unclosed-session warning."""
    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()

    async def _clean() -> HttpClient:
        client = HttpClient(sq, {})
        await client._ensure_session()
        await client.close()
        return client

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = asyncio.run(_clean())
        del client
        gc.collect()

    assert [str(w.message) for w in caught if issubclass(w.category, ResourceWarning)] == []
