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

import logging

from rampa._types import Sample
from rampa.config import Config, ScenarioConfig, Stage
from rampa.loader import scenario
from rampa.worker import Worker

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Config",
    "Sample",
    "ScenarioConfig",
    "Stage",
    "Worker",
    "scenario",
]
