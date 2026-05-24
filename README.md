# rampa

[![Python versions](https://img.shields.io/pypi/pyversions/rampa.svg)](https://pypi.org/project/rampa/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Python 3.14+ async load testing framework with headless engine, typed
metrics, threshold policies, and six executor types matching k6's
scheduling models.

> **Pre-alpha.** APIs may change.

## Installation

```console
$ uv add rampa
```

## Quick Start

Write a test script:

```python
import rampa


@rampa.scenario(executor="constant-vus", vus=10, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://test.k6.io")
    worker.check(resp, {
        "status is 200": lambda r: r.status == 200,
    })
```

Run it:

```console
$ rampa run load_test.py
```

## Full Example

```python
import rampa
from rampa import Config, Scenario

config = Config(
    scenarios={
        "load": rampa.ScenarioConfig(
            executor="ramping-arrival-rate",
            rate=10.0,
            stages=[
                rampa.Stage(duration="1m", target=100),
            ],
            pre_allocated_vus=50,
            max_vus=200,
        ),
    },
    thresholds={
        "http_req_duration": ["p(95)<500"],
        "http_req_failed": ["rate<0.01"],
    },
)


async def setup() -> dict:
    return {"base_url": "https://staging.example.com"}


@rampa.scenario("load")
async def load_test(worker: rampa.Worker) -> None:
    resp = await worker.http.get(
        f"{worker.setup_data['base_url']}/api/users"
    )
    worker.check(resp, {
        "status is 200": lambda r: r.status == 200,
        "body has users": lambda r: len(r.json()["users"]) > 0,
    })
```

## Headless Engine API

For programmatic use (pytest, TUI, MCP, CI):

```python
import asyncio
import rampa

plan = rampa.loader.load_test("load_test.py")
controller = await rampa.Engine(plan).start()

# Poll metrics while running
snapshot = controller.snapshot()

# Or consume events
async for event in controller.events():
    print(event)

result = await controller.wait()
print(result.status)  # RunStatus.PASSED / THRESHOLD_FAILED / ...
```

## CLI

```console
$ rampa run script.py --vus 10 --duration 30s --out result.json
```

Exit codes: 0 = passed, 1 = threshold failed, 2 = iteration error,
3 = invalid config, 4 = aborted, 5 = setup failure.

## Executors

| Executor | Model | Description |
|----------|-------|-------------|
| `constant-vus` | Closed | Fixed N workers for a duration |
| `ramping-vus` | Closed | Linear VU ramp between stages |
| `shared-iterations` | Closed | N VUs share M total iterations |
| `per-vu-iterations` | Closed | Each VU runs exactly N iterations |
| `constant-arrival-rate` | Open | Timer-based scheduling, dropped iterations |
| `ramping-arrival-rate` | Open | Rate interpolation between stages |

## Links

- Source: <https://github.com/tony/rampa>
- Issues: <https://github.com/tony/rampa/issues>
- Docs: <https://rampa.git-pull.com/>
- Changelog: [CHANGES](CHANGES)
- License: [MIT](LICENSE)
