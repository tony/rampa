(index)=

# rampa

Async Python load testing, inspired by [k6](https://k6.io/).

Write an async scenario function, run it, get request metrics with
percentiles, checks, thresholds, and correct exit codes.

```{cli-install}
:variant: compact
```

```{mcp-install}
:variant: compact
```

## Your first load test

```python
import asyncio
import rampa

@rampa.scenario(executor="constant-vus", vus=10, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://httpbin.org/get")
    worker.check(resp, {"status is 200": lambda r: r.status == 200})
```

```console
$ rampa run load_test.py
```

::::{grid} 1 1 2 3
:gutter: 2 2 3 3

:::{grid-item-card} Quickstart
:link: getting-started/index
:link-type: doc
Write and run your first scenario in 60 seconds.
:::

:::{grid-item-card} CLI
:link: cli/index
:link-type: doc
{doc}`cli/run`, {doc}`cli/check`, and {doc}`cli/doctor` from the terminal.
:::

:::{grid-item-card} Library
:link: library/index
:link-type: doc
Executors, metrics, thresholds, and the Python API.
:::

:::{grid-item-card} pytest
:link: pytest/index
:link-type: doc
Run load tests inside your test suite with the
{ref}`pytest scenario marker <pytest-scenario-marker>`.
:::

:::{grid-item-card} MCP
:link: mcp/index
:link-type: doc
Start, stop, and query load tests from AI agents.
:::

:::{grid-item-card} Development
:link: dev/index
:link-type: doc
Contributing, benchmarks, and architecture.
:::

::::

## What you get

### Six executor types

Closed-model (VU-based) and open-model (arrival-rate) scheduling,
matching k6's executor vocabulary.

| Executor | Model | Use when |
|----------|-------|----------|
| `constant-vus` | Closed | Fixed concurrency for a duration |
| `ramping-vus` | Closed | Ramp concurrency up/down through stages |
| `shared-iterations` | Closed | Run exactly N total iterations |
| `per-vu-iterations` | Closed | Each VU runs exactly N iterations |
| `constant-arrival-rate` | Open | Maintain a fixed request rate |
| `ramping-arrival-rate` | Open | Ramp request rate through stages |

### Automatic HTTP metrics

Every HTTP request auto-emits timing metrics with per-phase
decomposition (blocked, connecting, sending, waiting, receiving),
failure classification, and data transfer counters.

### Threshold expressions

```python
config = rampa.Config(
    thresholds={
        "http_req_duration": ["p(95)<500", "avg<200"],
        "http_req_failed": ["rate<0.01"],
    },
)
```

Threshold breaches produce exit code 1 for CI integration.

### Multiple frontends and outputs

- **CLI** — {doc}`cli/run` with `--progress` live status or `--tui` dashboard
- **TUI** — {doc}`library/tui` with live metrics and keyboard control
- **pytest plugin** — {doc}`pytest/index` with the {ref}`pytest scenario marker <pytest-scenario-marker>`
- **unittest mixin** — {class}`~rampa.unittest_plugin.RampaTestCase` for
  unittest integration
- **MCP server** — {doc}`mcp/index` for AI agent integration
- **Output backends** — {doc}`library/outputs` via `--output`
- **CI comparison** — {mod}`rampa.ci.compare` for benchmark diffs

```{toctree}
:hidden:

getting-started/index
cli/index
library/index
pytest/index
mcp/index
dev/index
history
GitHub <https://github.com/tony/rampa>
```
