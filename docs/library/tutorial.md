(tutorial)=

# Tutorial

Build a load test step by step — from a minimal scenario to a
complete test with checks, thresholds, and structured output.

## Minimal scenario

A rampa scenario is an async function decorated with {func}`~rampa.loader.scenario`.
It receives a {class}`~rampa.worker.Worker` and runs one iteration of your
workload.

```python
import asyncio
import rampa


@rampa.scenario(executor="constant-vus", vus=1, duration="5s")
async def default(worker: rampa.Worker) -> None:
    await asyncio.sleep(0.01)
```

```console
$ rampa run load_test.py
```

If this covers your test, you can stop here. The rest of the tutorial
adds HTTP metrics, checks, thresholds, and multi-scenario structure.

## HTTP requests

The worker provides {attr}`~rampa.worker.Worker.http`, an HTTP client
that auto-emits timing metrics:

```python
@rampa.scenario(executor="constant-vus", vus=5, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://httpbin.org/get")
```

Every request emits `http_reqs`, `http_req_duration`, `http_req_failed`,
data transfer counters, and per-phase timing metrics automatically.

## Checks

{meth}`~rampa.worker.Worker.check` validates response properties. Each
condition emits a pass/fail sample on the `checks` metric:

```python
@rampa.scenario(executor="constant-vus", vus=5, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://httpbin.org/get")
    worker.check(resp, {
        "status is 200": lambda r: r.status == 200,
        "body is JSON": lambda r: r.json() is not None,
    })
```

## Thresholds

{class}`~rampa.config.Config` thresholds define pass/fail criteria. A
breach produces exit code 1:

```python
config = rampa.Config(
    thresholds={
        "http_req_duration": ["p(95)<500", "avg<200"],
        "http_req_failed": ["rate<0.01"],
        "checks": ["rate>0.99"],
    },
)
```

## Custom metrics

Emit your own counters, gauges, and trends with
{meth}`~rampa.worker.Worker.counter`,
{meth}`~rampa.worker.Worker.gauge`, and
{meth}`~rampa.worker.Worker.trend`:

```python
@rampa.scenario(executor="constant-vus", vus=5, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://api.example.com/items")
    items = resp.json()
    worker.gauge("items_returned", float(len(items)))
    worker.counter("api_calls")
```

## Setup and teardown

Module-level `setup()` and `teardown()` functions run once:

```python
async def setup():
    return {"token": "abc123"}


async def teardown():
    pass


@rampa.scenario(executor="constant-vus", vus=5, duration="30s")
async def default(worker: rampa.Worker) -> None:
    token = worker.setup_data["token"]
    await worker.http.get(
        "https://api.example.com/data",
        headers={"Authorization": f"Bearer {token}"},
    )
```

## Multiple scenarios

A single script can define multiple scenarios:

```python
@rampa.scenario(
    name="smoke",
    executor="constant-vus",
    vus=1,
    duration="10s",
)
async def smoke(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/health")


@rampa.scenario(
    name="load",
    executor="ramping-vus",
    stages=[
        rampa.Stage(duration="30s", target=50),
        rampa.Stage(duration="1m", target=100),
        rampa.Stage(duration="30s", target=0),
    ],
)
async def load(worker: rampa.Worker) -> None:
    await worker.http.post(
        "https://api.example.com/data",
        json={"key": "value"},
    )
```

Run a specific scenario:

```console
$ rampa run load_test.py --scenario smoke
```
