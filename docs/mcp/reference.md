(mcp-reference)=

# API Reference

FastMCP server factory, run registry, event models, and
configuration types used by the MCP tools and resources.

## Server

```{eval-rst}
.. autofunction:: rampa.mcp.server.build_mcp_server
.. autofunction:: rampa.mcp.server.main
```

## Registry

```{eval-rst}
.. autoclass:: rampa.mcp.registry.RunRecord
   :members:

.. autoclass:: rampa.mcp.registry.RuntimeRun
   :members:

.. autoclass:: rampa.mcp.registry.RunRegistry
   :members:
```

## Events

The tools and resources hand back rampa's own event types, which the
library {ref}`api-reference` documents: a finished run arrives as a
{class}`~rampa.events.RunResult` carrying a
{class}`~rampa.events.RunStatus`, and a live run streams
{class}`~rampa.events.PhaseEvent`,
{class}`~rampa.events.SnapshotEvent`, and
{class}`~rampa.events.ThresholdEvent`.

## Configuration

You describe a run with the same {class}`~rampa.config.Config` the CLI
loads, built from {class}`~rampa.config.ScenarioConfig` entries and
their {class}`~rampa.config.Stage` ramps.

## Metrics

Metric and threshold queries answer with a
{class}`~rampa.metrics.MetricSnapshot`, a
{class}`~rampa.thresholds.ThresholdResult` per threshold, and the
{class}`~rampa.thresholds.ThresholdExpression` each one was parsed
from.
