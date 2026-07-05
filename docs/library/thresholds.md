(thresholds)=

# Thresholds

Thresholds define pass/fail criteria for your load test. When any
threshold breaches, `rampa run` exits with code 1.

## Syntax

```
<aggregation>[(<parameter>)] <operator> <value>
```

## Aggregation functions

| Function | Metric types | Description |
|----------|-------------|-------------|
| `avg` | Trend | Mean value |
| `min` | Trend | Minimum value |
| `max` | Trend | Maximum value |
| `med` | Trend | Median (p50) |
| `p(N)` | Trend | Nth percentile (e.g. `p(95)`) |
| `count` | Counter | Total count |
| `rate` | Rate | Pass ratio (0.0–1.0) |
| `value` | Gauge | Current value |

## Operators

`<`, `<=`, `>`, `>=`, `==`, `!=`

## Examples

Put threshold expressions in a module-level
{class}`~rampa.config.Config`:

```python
config = rampa.Config(
    thresholds={
        "http_req_duration": [
            "p(95)<500",    # 95th percentile under 500ms
            "avg<200",      # Average under 200ms
            "max<2000",     # No request over 2 seconds
        ],
        "http_req_failed": [
            "rate<0.01",    # Less than 1% failure rate
        ],
        "checks": [
            "rate>0.99",    # At least 99% of checks pass
        ],
        "iterations": [
            "count>=100",   # At least 100 iterations completed
        ],
    },
)
```

## In a script

Define `config` at module level, then add a
{func}`~rampa.loader.scenario` that receives a
{class}`~rampa.worker.Worker`:

```python
import rampa

config = rampa.Config(
    thresholds={
        "http_req_duration": ["p(95)<500"],
    },
)


@rampa.scenario(executor="constant-vus", vus=10, duration="30s")
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```
