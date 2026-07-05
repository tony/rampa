(metrics)=

# Metrics

rampa automatically collects metrics for every iteration and HTTP
request. You can also emit custom metrics from your scenario code.

## Built-in metrics

### Execution metrics

| Metric | Type | Description |
|--------|------|-------------|
| `iterations` | Counter | Completed iterations |
| `iteration_duration` | Trend | Time per iteration (ms) |
| `iteration_errors` | Counter | Failed iterations |
| `dropped_iterations` | Counter | Skipped iterations (arrival-rate) |
| `vus` | Gauge | Active virtual users |
| `vus_max` | Gauge | Peak virtual users |

### HTTP metrics

| Metric | Type | Description |
|--------|------|-------------|
| `http_reqs` | Counter | Completed HTTP requests |
| `http_req_duration` | Trend | Total request time (ms) |
| `http_req_failed` | Rate | Failure ratio |
| `data_sent` | Counter | Bytes sent |
| `data_received` | Counter | Bytes received |

### HTTP phase timing

| Metric | Type | Description |
|--------|------|-------------|
| `http_req_blocked` | Trend | DNS + connection queue (ms) |
| `http_req_connecting` | Trend | TCP connection (ms) |
| `http_req_sending` | Trend | Request send (ms) |
| `http_req_waiting` | Trend | Time to first byte (ms) |
| `http_req_receiving` | Trend | Response receive (ms) |

### Check metrics

| Metric | Type | Description |
|--------|------|-------------|
| `checks` | Rate | Check pass ratio |

## Metric types

| Type | Tracks | Aggregations |
|------|--------|-------------|
| **Counter** | Cumulative total | count, rate |
| **Gauge** | Current value | value, min, max |
| **Rate** | Success ratio | rate, passes, fails |
| **Trend** | Distribution | count, avg, min, max, med, p(90), p(95), p(99) |

## Custom metrics

Emit custom metrics from your scenario with
{meth}`~rampa.worker.Worker.counter`,
{meth}`~rampa.worker.Worker.gauge`, and
{meth}`~rampa.worker.Worker.trend`:

```python
@rampa.scenario(executor="constant-vus", vus=5, duration="30s")
async def default(worker: rampa.Worker) -> None:
    resp = await worker.http.get("https://api.example.com/items")
    items = resp.json()

    worker.counter("api_calls")
    worker.gauge("items_returned", float(len(items)))
    worker.trend("processing_time", 42.5)
```

Custom metrics appear in the console summary and JSON output alongside
built-in metrics.
