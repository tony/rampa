(mcp)=

# MCP Server

The `rampa-mcp` server lets AI agents inspect, start, control, and
query load tests via the Model Context Protocol.

```{mcp-install}
```

::::{grid} 1 1 3 3
:gutter: 2 2 3 3

:::{grid-item-card} Tools
:link: tools
:link-type: doc
Inspect scripts, control runs, and query load test results.
:::

:::{grid-item-card} Resources
:link: resources
:link-type: doc
URI templates for runs, metrics, and thresholds.
:::

:::{grid-item-card} API Reference
:link: reference
:link-type: doc
Server factory, run registry, and models.
:::

::::

## What you can do

### Load Testing

Start and manage load test runs from AI agents.
{ref}`fastmcp-tool-start-run` · {ref}`fastmcp-tool-stop-run` · {ref}`fastmcp-tool-pause-run` · {ref}`fastmcp-tool-resume-run` · {ref}`fastmcp-tool-get-status` · {ref}`fastmcp-tool-list-runs`

### Discovery

Inspect scripts before you run them.
{ref}`fastmcp-tool-discover-scenarios` · {ref}`fastmcp-tool-inspect-config`

### Observability

Query metrics and threshold results for completed runs.
{ref}`fastmcp-tool-get-metrics` · {ref}`fastmcp-tool-get-thresholds`

```{toctree}
:hidden:

tools
resources
reference
```
