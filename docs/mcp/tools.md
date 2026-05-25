(mcp-tools)=

# Tools

The rampa MCP server provides six tools for load test lifecycle
management, metric retrieval, and threshold evaluation.

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
