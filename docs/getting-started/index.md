(getting-started)=

# Getting Started

Write and run your first load test in 60 seconds.

## Install

::::{tab-set}

:::{tab-item} uv
```console
$ uv add rampa
```
:::

:::{tab-item} pip
```console
$ pip install rampa
```
:::

::::

Verify:

```console
$ rampa doctor
```

## Write a scenario

Create `load_test.py`:

```python
import asyncio
import rampa


@rampa.scenario(executor="constant-vus", vus=5, duration="10s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://httpbin.org/get")
    worker.check(resp, {
        "status is 200": lambda r: r.status == 200,
    })
```

## Run it

```console
$ rampa run load_test.py
```

The console summary shows iteration count, request timing percentiles
(p90, p95, p99), check pass/fail rates, and data transfer totals.

## Add thresholds

Thresholds enforce performance criteria. A breach produces exit code 1.

```python
config = rampa.Config(
    thresholds={
        "http_req_duration": ["p(95)<500"],
        "http_req_failed": ["rate<0.01"],
    },
)
```

## Save results

```console
$ rampa run load_test.py --out results.json
```

```console
$ rampa run load_test.py --event-log events.jsonl
```

## Next steps

- {doc}`../cli/index` — all CLI flags and commands
- {doc}`../library/executors` — choosing the right executor
- {doc}`../library/metrics` — built-in and custom metrics
- {doc}`../pytest/index` — load tests in your test suite

```{toctree}
:hidden:

installation
```
