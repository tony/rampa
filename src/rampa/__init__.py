"""rampa — Python load testing framework.

>>> import rampa
>>> hasattr(rampa, "scenario")
True
>>> hasattr(rampa, "Config")
True
>>> hasattr(rampa, "Worker")
True
>>> hasattr(rampa, "Engine")
True
>>> hasattr(rampa, "RunController")
True
"""

from __future__ import annotations

import logging

from rampa._types import Sample
from rampa.config import Config, ScenarioConfig, Stage
from rampa.engine import Engine, EngineOptions, RunController
from rampa.events import RunResult, RunStatus
from rampa.loader import scenario
from rampa.worker import Worker

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Config",
    "Engine",
    "EngineOptions",
    "RunController",
    "RunResult",
    "RunStatus",
    "Sample",
    "ScenarioConfig",
    "Stage",
    "Worker",
    "scenario",
]
