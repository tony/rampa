(mcp-tools)=

# MCP Tools

The rampa MCP server provides six tools for load test lifecycle
management.

## start_run

Start a new load test from a script path.

| Parameter | Type | Description |
|-----------|------|-------------|
| `script_path` | string | Path to the test script |
| `vus` | int (optional) | Override VU count |
| `duration` | string (optional) | Override duration |
| `scenario` | string (optional) | Run a specific scenario |

Returns: `run_id`, initial status.

## stop_run

Stop a running test gracefully.

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | string | The run to stop |
| `reason` | string (optional) | Stop reason |

## get_status

Poll the current status of a run.

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | string | The run to query |

Returns: status, elapsed time, iteration count.

## list_runs

List all completed and active runs.

Returns: array of run summaries with `run_id`, `status`, `script_path`.

## get_metrics

Retrieve the latest metric snapshot for a run.

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | string | The run to query |
| `metric` | string (optional) | Filter to a specific metric |

Returns: metric values with aggregations.

## get_thresholds

Evaluate threshold results for a completed run.

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | string | The run to query |

Returns: threshold pass/fail results with actual vs expected values.
