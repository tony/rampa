(pytest-plugin)=

# pytest Plugin

Run load tests inside your existing test suite. The plugin provides
a marker for scenario configuration and a fixture that returns the
run result.

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item-card} API Reference
:link: reference
:link-type: doc
Fixture and marker reference.
:::

::::

## Install

rampa registers as a pytest plugin via the `pytest11` entry point.
No configuration needed — install rampa and the plugin activates.

## Usage

```python
import pytest
from rampa.events import RunResult, RunStatus


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=2,
    duration="500ms",
    worker_fn=my_worker,
)
def test_api_performance(rampa_result: RunResult) -> None:
    assert rampa_result.status == RunStatus.PASSED
```

## Marker: `@pytest.mark.rampa_scenario`

The marker accepts the same keyword arguments as
{class}`~rampa.config.ScenarioConfig` plus:

| Kwarg | Type | Description |
|-------|------|-------------|
| `worker_fn` | async callable | The scenario function (required) |
| `thresholds` | dict | Threshold expressions per metric |

All `ScenarioConfig` fields work: `executor`, `vus`, `duration`,
`iterations`, `stages`, `rate`, `max_vus`.

## Fixture: `rampa_result`

The `rampa_result` fixture runs the scenario and returns a
{class}`~rampa.events.RunResult`. The fixture does not auto-fail on
threshold breach — assert on `result.status` in the test body.

```python
def test_thresholds(rampa_result: RunResult) -> None:
    assert rampa_result.status == RunStatus.PASSED
    assert len(rampa_result.threshold_results) > 0
    assert all(r.passed for r in rampa_result.threshold_results)
```

## Complete example

```python
import asyncio
import pytest
from rampa.events import RunResult, RunStatus
from rampa.worker import Worker


async def api_worker(w: Worker) -> None:
    await asyncio.sleep(0.001)
    w.counter("requests")


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=2,
    duration="200ms",
    worker_fn=api_worker,
    thresholds={"iteration_duration": ["avg<100"]},
)
def test_api_under_load(rampa_result: RunResult) -> None:
    assert rampa_result.status == RunStatus.PASSED
    assert rampa_result.snapshot is not None
```

```{toctree}
:hidden:

reference
```
