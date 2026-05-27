"""Protocol client implementations for rampa.

Each protocol provides a client class accessible via a Worker property.
Clients auto-emit protocol-specific metrics to the sample queue.

>>> import rampa.protocols
"""

from __future__ import annotations
