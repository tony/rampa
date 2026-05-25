(mcp-tools)=

# Tools

The rampa MCP server provides six tools for load test lifecycle
management, metric retrieval, and threshold evaluation.

::::{grid} 1 2 3 3
:gutter: 2 2 3 3

:::{grid-item-card} Start Run
:link: fastmcp-tool-start-run
:link-type: ref
Start a new load test from a script path.
:::

:::{grid-item-card} Stop Run
:link: fastmcp-tool-stop-run
:link-type: ref
Gracefully stop a running test.
:::

:::{grid-item-card} Get Status
:link: fastmcp-tool-get-status
:link-type: ref
Poll whether a run is active or completed.
:::

:::{grid-item-card} List Runs
:link: fastmcp-tool-list-runs
:link-type: ref
List all active and completed runs.
:::

:::{grid-item-card} Get Metrics
:link: fastmcp-tool-get-metrics
:link-type: ref
Retrieve metric snapshots with percentiles.
:::

:::{grid-item-card} Get Thresholds
:link: fastmcp-tool-get-thresholds
:link-type: ref
Evaluate threshold pass/fail results.
:::

::::

## Run Lifecycle

```{fastmcp-tool} start_run
```

Start a new load test from a script path. Returns the `run_id` and
initial status.

```{fastmcp-tool-input} start_run
```

```{fastmcp-tool} stop_run
```

Gracefully stop a running test. Idempotent — calling on a completed
run returns `already_completed`.

```{fastmcp-tool-input} stop_run
```

```{fastmcp-tool} get_status
```

Poll whether a run is still active or has completed.

```{fastmcp-tool-input} get_status
```

```{fastmcp-tool} list_runs
```

List all active and completed runs with their `run_id`, `status`,
and `script_path`.

## Metrics

```{fastmcp-tool} get_metrics
```

Retrieve the latest metric snapshot for a run. Without a
`metric_name` filter, returns all metrics including timing
percentiles, counters, and rates.

```{fastmcp-tool-input} get_metrics
```

## Thresholds

```{fastmcp-tool} get_thresholds
```

Evaluate threshold results for a completed run. Returns pass/fail
status with actual vs expected values for each threshold expression.

```{fastmcp-tool-input} get_thresholds
```
