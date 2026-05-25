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

```{eval-rst}
.. autoclass:: rampa.events.RunResult
   :members:
   :no-index:

.. autoclass:: rampa.events.RunStatus
   :members:
   :undoc-members:
   :no-index:

.. autoclass:: rampa.events.PhaseEvent
   :members:
   :no-index:

.. autoclass:: rampa.events.SnapshotEvent
   :members:
   :no-index:

.. autoclass:: rampa.events.ThresholdEvent
   :members:
   :no-index:
```

## Configuration

```{eval-rst}
.. autoclass:: rampa.config.Config
   :members:
   :no-index:

.. autoclass:: rampa.config.ScenarioConfig
   :members:
   :no-index:

.. autoclass:: rampa.config.Stage
   :members:
   :no-index:
```

## Metrics

```{eval-rst}
.. autoclass:: rampa.metrics.MetricSnapshot
   :members:
   :no-index:

.. autoclass:: rampa.thresholds.ThresholdResult
   :members:
   :no-index:

.. autoclass:: rampa.thresholds.ThresholdExpression
   :members:
   :no-index:
```
