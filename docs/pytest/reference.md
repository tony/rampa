(pytest-reference)=

# API Reference

:::{auto-pytest-plugin} rampa.pytest_plugin
:project: rampa
:package: rampa
:summary: rampa ships a pytest plugin for running load test scenarios inside your test suite.
:tests-url: https://github.com/tony/rampa/tree/main/tests

The plugin auto-registers via the `pytest11` entry point. Install rampa
and the marker and fixture activate without configuration.

## Quick start

```python
import pytest
from rampa.events import RunResult, RunStatus
from rampa.worker import Worker


async def my_worker(w: Worker) -> None:
    await w.http.get("https://httpbin.org/get")


@pytest.mark.rampa_scenario(
    executor="constant-vus",
    vus=2,
    duration="500ms",
    worker_fn=my_worker,
)
def test_api_performance(rampa_result: RunResult) -> None:
    assert rampa_result.status == RunStatus.PASSED
```
:::
