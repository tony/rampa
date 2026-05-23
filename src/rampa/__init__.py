"""rampa — Python load testing framework.

>>> import rampa
>>> hasattr(rampa, "scenario")
True
>>> hasattr(rampa, "Config")
True
>>> hasattr(rampa, "Worker")
True
"""

from __future__ import annotations

from rampa._types import Sample
from rampa.config import Config, ScenarioConfig, Stage
from rampa.loader import scenario
from rampa.worker import Worker

__all__ = [
    "Config",
    "Sample",
    "ScenarioConfig",
    "Stage",
    "Worker",
    "scenario",
]
