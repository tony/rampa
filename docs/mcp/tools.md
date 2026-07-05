(mcp-tools)=

# Tools

The rampa MCP server provides ten tools for load test lifecycle
management, scenario discovery, metric retrieval, and threshold
evaluation.

::::{grid} 1 2 3 5
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

:::{grid-item-card} Pause Run
:link: fastmcp-tool-pause-run
:link-type: ref
Pause a running test before the next iteration.
:::

:::{grid-item-card} Resume Run
:link: fastmcp-tool-resume-run
:link-type: ref
Resume a paused test.
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

:::{grid-item-card} Discover Scenarios
:link: fastmcp-tool-discover-scenarios
:link-type: ref
Inspect scenarios without starting a run.
:::

:::{grid-item-card} Inspect Config
:link: fastmcp-tool-inspect-config
:link-type: ref
Show resolved configuration without starting a run.
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

```{fastmcp-tool} pause_run
```

Pause a running test. Executors block before the next iteration.

```{fastmcp-tool-input} pause_run
```

```{fastmcp-tool} resume_run
```

Resume a paused test.

```{fastmcp-tool-input} resume_run
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

## Discovery

```{fastmcp-tool} discover_scenarios
```

Load a script and list its scenarios, thresholds, and lifecycle hooks
without starting a run.

```{fastmcp-tool-input} discover_scenarios
```

```{fastmcp-tool} inspect_config
```

Show the fully resolved test configuration for a script without
starting a run.

```{fastmcp-tool-input} inspect_config
```

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
