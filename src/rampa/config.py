"""User-facing configuration models for rampa.

All scenario, executor, threshold, and option configuration is defined here as
pydantic models with validation. These models are the user's primary interface
for configuring load tests.

>>> import rampa.config
"""

from __future__ import annotations

import datetime
import re
import typing as t

from pydantic import BaseModel, BeforeValidator, field_validator, model_validator

_DURATION_RE = re.compile(
    r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?(?:(\d+)ms)?$",
)


def parse_duration(value: str | datetime.timedelta) -> datetime.timedelta:
    """Parse a human-readable duration string into a timedelta.

    Supports ``h``, ``m``, ``s``, and ``ms`` components. At least one component
    must be present.

    Parameters
    ----------
    value : str | datetime.timedelta
        Duration string (e.g. ``"30s"``, ``"1m30s"``, ``"2h"``) or an existing
        timedelta.

    Returns
    -------
    datetime.timedelta
        Parsed duration.

    Raises
    ------
    ValueError
        If the string cannot be parsed.

    >>> parse_duration("30s")
    datetime.timedelta(seconds=30)
    >>> parse_duration("1m30s")
    datetime.timedelta(seconds=90)
    >>> parse_duration("2h")
    datetime.timedelta(seconds=7200)
    >>> parse_duration("500ms")
    datetime.timedelta(microseconds=500000)
    >>> parse_duration("1h30m15s")
    datetime.timedelta(seconds=5415)
    >>> parse_duration(datetime.timedelta(seconds=10))
    datetime.timedelta(seconds=10)
    """
    if isinstance(value, datetime.timedelta):
        return value
    match = _DURATION_RE.match(value)
    if not match or not any(match.groups()):
        msg = f"invalid duration: {value!r}"
        raise ValueError(msg)
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    milliseconds = int(match.group(4) or 0)
    return datetime.timedelta(
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        milliseconds=milliseconds,
    )


Duration = t.Annotated[datetime.timedelta, BeforeValidator(parse_duration)]
"""A timedelta that can be constructed from a human-readable string."""


class Stage(BaseModel, frozen=True):
    """A single ramp stage with a target VU or rate count and duration.

    >>> import datetime
    >>> Stage(
    ...     duration=datetime.timedelta(seconds=30), target=100,
    ... ).target
    100
    >>> Stage(
    ...     duration=datetime.timedelta(minutes=1), target=0,
    ... ).duration
    datetime.timedelta(seconds=60)
    """

    duration: Duration
    target: int


class ScenarioConfig(BaseModel):
    """Configuration for a single test scenario.

    Each scenario maps to an executor that controls how iterations are
    scheduled. Executor-specific fields are validated by the executor, not by
    this model.

    >>> import datetime
    >>> cfg = ScenarioConfig(
    ...     executor="constant-vus",
    ...     vus=10,
    ...     duration=datetime.timedelta(seconds=30),
    ... )
    >>> cfg.executor
    'constant-vus'
    >>> cfg.vus
    10
    """

    executor: str
    vus: int | None = None
    duration: Duration | None = None
    iterations: int | None = None
    stages: list[Stage] | None = None
    rate: float | None = None
    time_unit: Duration = datetime.timedelta(seconds=1)
    pre_allocated_vus: int | None = None
    max_vus: int | None = None
    exec_fn: str = "default"
    start_time: Duration = datetime.timedelta(0)
    graceful_stop: Duration = datetime.timedelta(seconds=30)
    tags: dict[str, str] = {}
    env: dict[str, str] = {}


class Options(BaseModel):
    """Shortcut execution options.

    These provide a simpler alternative to explicit ``scenarios`` for common
    cases. When both shortcuts and ``scenarios`` are provided, validation
    rejects the config.

    >>> import datetime
    >>> Options(
    ...     vus=10, duration=datetime.timedelta(seconds=30),
    ... ).vus
    10
    """

    vus: int | None = None
    duration: Duration | None = None
    iterations: int | None = None
    stages: list[Stage] | None = None
    tags: dict[str, str] = {}
    setup_timeout: Duration = datetime.timedelta(seconds=60)
    teardown_timeout: Duration = datetime.timedelta(seconds=60)


class Config(BaseModel):
    """Top-level test configuration.

    Either ``scenarios`` or shortcut options (``vus``, ``duration``, etc.) may
    be provided, but not both.

    >>> import datetime
    >>> cfg = Config(
    ...     scenarios={"smoke": ScenarioConfig(
    ...         executor="constant-vus",
    ...         vus=1,
    ...         duration=datetime.timedelta(seconds=10),
    ...     )},
    ... )
    >>> "smoke" in cfg.scenarios
    True
    >>> cfg.scenarios["smoke"].executor
    'constant-vus'
    """

    scenarios: dict[str, ScenarioConfig] = {}
    thresholds: dict[str, list[str]] = {}
    options: Options = Options()

    @field_validator("thresholds")
    @classmethod
    def _validate_threshold_expressions(
        cls,
        v: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        for metric_name, expressions in v.items():
            if not expressions:
                msg = f"threshold for {metric_name!r} has no expressions"
                raise ValueError(msg)
            for expr in expressions:
                if not isinstance(expr, str) or not expr.strip():
                    msg = f"threshold expression must be a non-empty string, got {expr!r}"
                    raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _validate_no_shortcut_with_scenarios(self) -> Config:
        has_scenarios = bool(self.scenarios)
        opts = self.options
        has_shortcuts = any(
            [
                opts.vus is not None,
                opts.duration is not None,
                opts.iterations is not None,
                opts.stages is not None,
            ]
        )
        if has_scenarios and has_shortcuts:
            msg = (
                "cannot use both 'scenarios' and shortcut options "
                "(vus, duration, iterations, stages) at the same time"
            )
            raise ValueError(msg)
        return self
