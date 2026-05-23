"""Tests for rampa configuration models."""

from __future__ import annotations

import datetime
import typing as t

import pytest

from rampa.config import (
    Config,
    Options,
    ScenarioConfig,
    Stage,
    parse_duration,
)


class ParseDurationFixture(t.NamedTuple):
    """Test case for parse_duration()."""

    test_id: str
    value: str | datetime.timedelta
    expected: datetime.timedelta


_PARSE_DURATION_FIXTURES: list[ParseDurationFixture] = [
    ParseDurationFixture("seconds", "30s", datetime.timedelta(seconds=30)),
    ParseDurationFixture("minutes", "5m", datetime.timedelta(minutes=5)),
    ParseDurationFixture("hours", "2h", datetime.timedelta(hours=2)),
    ParseDurationFixture("milliseconds", "500ms", datetime.timedelta(milliseconds=500)),
    ParseDurationFixture(
        "combined",
        "1h30m15s",
        datetime.timedelta(hours=1, minutes=30, seconds=15),
    ),
    ParseDurationFixture("minutes_seconds", "1m30s", datetime.timedelta(seconds=90)),
    ParseDurationFixture(
        "passthrough",
        datetime.timedelta(seconds=42),
        datetime.timedelta(seconds=42),
    ),
]


@pytest.mark.parametrize(
    list(ParseDurationFixture._fields),
    _PARSE_DURATION_FIXTURES,
    ids=[f.test_id for f in _PARSE_DURATION_FIXTURES],
)
def test_parse_duration(
    test_id: str,
    value: str | datetime.timedelta,
    expected: datetime.timedelta,
) -> None:
    """parse_duration() converts strings and passthroughs correctly."""
    assert parse_duration(value) == expected


class InvalidDurationFixture(t.NamedTuple):
    """Test case for invalid duration strings."""

    test_id: str
    value: str


_INVALID_DURATIONS: list[InvalidDurationFixture] = [
    InvalidDurationFixture("empty", ""),
    InvalidDurationFixture("no_unit", "30"),
    InvalidDurationFixture("bad_unit", "30x"),
    InvalidDurationFixture("text", "thirty seconds"),
]


@pytest.mark.parametrize(
    list(InvalidDurationFixture._fields),
    _INVALID_DURATIONS,
    ids=[f.test_id for f in _INVALID_DURATIONS],
)
def test_parse_duration_rejects_invalid(test_id: str, value: str) -> None:
    """parse_duration() raises ValueError for invalid inputs."""
    with pytest.raises(ValueError, match="invalid duration"):
        parse_duration(value)


def test_stage_creation() -> None:
    """Stage parses duration strings and stores target."""
    stage = Stage(duration="1m", target=100)  # ty: ignore[invalid-argument-type]
    assert stage.duration == datetime.timedelta(minutes=1)
    assert stage.target == 100


def test_scenario_config_defaults() -> None:
    """ScenarioConfig has sensible defaults for optional fields."""
    cfg = ScenarioConfig(executor="constant-vus")
    assert cfg.vus is None
    assert cfg.duration is None
    assert cfg.exec_fn == "default"
    assert cfg.graceful_stop == datetime.timedelta(seconds=30)
    assert cfg.tags == {}


def test_scenario_config_with_duration() -> None:
    """ScenarioConfig parses duration strings."""
    cfg = ScenarioConfig(executor="constant-vus", vus=10, duration="30s")  # ty: ignore[invalid-argument-type]
    assert cfg.duration == datetime.timedelta(seconds=30)


def test_config_scenarios_only() -> None:
    """Config accepts scenarios without shortcut options."""
    cfg = Config(
        scenarios={
            "smoke": ScenarioConfig(executor="constant-vus", vus=1, duration="10s"),  # ty: ignore[invalid-argument-type]
        },
    )
    assert "smoke" in cfg.scenarios


def test_config_options_only() -> None:
    """Config accepts shortcut options without scenarios."""
    cfg = Config(options=Options(vus=10, duration="30s"))  # ty: ignore[invalid-argument-type]
    assert cfg.options.vus == 10
    assert cfg.scenarios == {}


def test_config_rejects_both_scenarios_and_shortcuts() -> None:
    """Config rejects when both scenarios and shortcut options are provided."""
    with pytest.raises(ValueError, match="cannot use both"):
        Config(
            scenarios={
                "smoke": ScenarioConfig(executor="constant-vus", vus=1, duration="10s"),  # ty: ignore[invalid-argument-type]
            },
            options=Options(vus=10, duration="30s"),  # ty: ignore[invalid-argument-type]
        )


def test_config_empty_threshold_expressions_rejected() -> None:
    """Config rejects threshold entries with empty expression lists."""
    with pytest.raises(ValueError, match="has no expressions"):
        Config(thresholds={"http_req_duration": []})


def test_config_blank_threshold_expression_rejected() -> None:
    """Config rejects blank threshold expression strings."""
    with pytest.raises(ValueError, match="non-empty string"):
        Config(thresholds={"http_req_duration": [""]})


def test_config_valid_thresholds() -> None:
    """Config accepts valid threshold expressions."""
    cfg = Config(
        thresholds={
            "http_req_duration": ["p(95)<500", "avg<200"],
            "http_req_failed": ["rate<0.01"],
        },
    )
    assert len(cfg.thresholds["http_req_duration"]) == 2
