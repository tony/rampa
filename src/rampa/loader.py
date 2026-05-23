"""Test script loader and ``@scenario`` decorator for rampa.

Discovers scenario functions, setup, and teardown from user Python modules.

>>> import rampa.loader
"""

from __future__ import annotations

import importlib.util
import sys
import typing as t
from dataclasses import dataclass

from rampa.config import Config, ScenarioConfig

_SCENARIO_ATTR = "_rampa_scenario_config"


def scenario(
    name: str | None = None,
    **kwargs: t.Any,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """Mark an async function as a rampa scenario.

    Parameters
    ----------
    name : str | None
        Scenario name. Defaults to the function name.
    **kwargs : Any
        ScenarioConfig fields (executor, vus, duration, etc.).

    Returns
    -------
    Callable
        The decorated function with scenario metadata attached.

    >>> @scenario(executor="constant-vus", vus=5, duration="10s")
    ... async def load_test(worker: object) -> None:
    ...     pass
    >>> hasattr(load_test, "_rampa_scenario_config")
    True
    """

    def decorator(fn: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        scenario_name = name or getattr(fn, "__name__", "default")
        if "executor" not in kwargs:
            kwargs["executor"] = "constant-vus"
        config = ScenarioConfig(**kwargs)
        setattr(fn, _SCENARIO_ATTR, (scenario_name, config))
        return fn

    return decorator


@dataclass
class TestPlan:
    """Resolved test plan ready for execution.

    >>> plan = TestPlan(scenarios={}, config=Config())
    >>> plan.setup_fn is None
    True
    """

    scenarios: dict[str, tuple[ScenarioConfig, t.Callable[..., t.Any]]]
    config: Config
    setup_fn: t.Callable[..., t.Any] | None = None
    teardown_fn: t.Callable[..., t.Any] | None = None


def load_test(path: str) -> TestPlan:
    """Load a test module and extract the test plan.

    Parameters
    ----------
    path : str
        Path to the Python test script.

    Returns
    -------
    TestPlan
        Resolved test plan with scenarios, setup, teardown, and config.

    Raises
    ------
    FileNotFoundError
        If the script file does not exist.
    ValueError
        If no scenarios are found.
    """
    import pathlib

    script_path = pathlib.Path(path)
    if not script_path.exists():
        msg = f"test script not found: {path}"
        raise FileNotFoundError(msg)

    module_name = f"_rampa_test_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        msg = f"cannot load module from: {path}"
        raise ValueError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    scenarios: dict[str, tuple[ScenarioConfig, t.Callable[..., t.Any]]] = {}
    config = getattr(module, "config", None)
    if config is None:
        config = Config()

    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if hasattr(obj, _SCENARIO_ATTR):
            scenario_name, scenario_config = getattr(obj, _SCENARIO_ATTR)
            scenarios[scenario_name] = (scenario_config, obj)

    if not scenarios and config.scenarios:
        default_fn = getattr(module, "default", None)
        if default_fn is not None:
            for sname, scfg in config.scenarios.items():
                fn = getattr(module, scfg.exec_fn, default_fn)
                scenarios[sname] = (scfg, fn)

    if not scenarios:
        msg = f"no scenarios found in {path}"
        raise ValueError(msg)

    setup_fn = getattr(module, "setup", None)
    teardown_fn = getattr(module, "teardown", None)

    return TestPlan(
        scenarios=scenarios,
        config=config if isinstance(config, Config) else Config(),
        setup_fn=setup_fn,
        teardown_fn=teardown_fn,
    )
