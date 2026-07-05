(mcp-resources)=

# Resources

MCP resources expose passive read-only data at `rampa://` URIs.
Clients read them with `resources/read`.

::::{grid} 1 2 3 3
:gutter: 2 2 3 3

:::{grid-item-card} All Runs
:link: fastmcp-resource-all-runs
:link-type: ref
List every active and completed run.
:::

:::{grid-item-card} Run Details
:link: fastmcp-resource-template-run-details
:link-type: ref
Status, script path, event count for one run.
:::

:::{grid-item-card} Run Metrics
:link: fastmcp-resource-template-run-metrics
:link-type: ref
All metrics for a run.
:::

:::{grid-item-card} Specific Metric
:link: fastmcp-resource-template-run-metric
:link-type: ref
Single metric by name.
:::

:::{grid-item-card} Threshold Results
:link: fastmcp-resource-template-run-thresholds
:link-type: ref
Pass/fail results for each threshold expression.
:::

:::{grid-item-card} Event Log
:link: fastmcp-resource-template-run-events
:link-type: ref
Accumulated event history for a run.
:::

::::

## All runs

```{fastmcp-resource} all_runs
```

Read `rampa://runs` to list every active and completed run with
their `run_id`, `script_path`, and current status.

## Run details

```{fastmcp-resource-template} run_details
```

Read `rampa://runs/{run_id}` for status, script path, completion
state, and event count.

## Run metrics

```{fastmcp-resource-template} run_metrics
```

Read `rampa://runs/{run_id}/metrics` for all metric values including
timing percentiles, counters, and rates.

## Specific metric

```{fastmcp-resource-template} run_metric
```

Read `rampa://runs/{run_id}/metrics/{name}` to retrieve a single
metric by name (e.g. `http_req_duration`, `http_reqs`).

## Threshold results

```{fastmcp-resource-template} run_thresholds
```

Read `rampa://runs/{run_id}/thresholds` for pass/fail results with
`source`, `passed`, `lhs` (actual), and `rhs` (expected) for each
threshold expression.

## Event log

```{fastmcp-resource-template} run_events
```

Read `rampa://runs/{run_id}/events` for the accumulated event
history including {class}`~rampa.events.PhaseEvent`,
{class}`~rampa.events.SnapshotEvent`, and
{class}`~rampa.events.ThresholdEvent` entries.
