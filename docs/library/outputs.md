(outputs)=

# Output backends

rampa ships metric samples to output backends during and after a test run.
Use `--output` to send results to multiple destinations simultaneously. Local
file backends create artifacts, remote backends deliver sample batches to
external stores, and CI backends present results inside the workflow.

## Built-in backends

| Backend | Storage / delivery | Covers | Dependencies |
|---|---|---|---|
| `console` | Terminal summary (default) | Final human-readable run summary | None |
| `json` | Local JSON file | Sample artifact, final summary, threshold results | None |
| `csv` | Local CSV file | One row per sample for spreadsheets or warehouse import | None |
| `influxdb` | InfluxDB HTTP line protocol | Time-series storage | aiohttp (included) |
| `prometheus` | Prometheus remote write | Prometheus/Grafana metric storage | aiohttp; optional `python-snappy` |
| `otel` | OTLP/HTTP JSON | OpenTelemetry collector pipeline | aiohttp (included) |
| `github` | GitHub Actions annotations and step summary | CI presentation, not durable metric storage | None |
| `webhook` | HTTP JSON batches | Custom ingestion services | aiohttp (included) |

## Storage shape

Use `json` or `csv` when the run needs a durable file artifact. Use
InfluxDB, Prometheus, OTEL, or webhook outputs when another system owns
retention, dashboards, or downstream ingestion. Use the GitHub Actions
surface for workflow summaries and annotations, usually alongside a JSON
artifact for comparison.

## CLI usage

```console
$ rampa run load_test.py --output csv=results.csv
```

Multiple outputs in one run:

```console
$ rampa run load_test.py \
  --output csv=results.csv \
  --output influxdb=http://localhost:8086/api/v2/write?org=myorg&bucket=rampa
```

The `--out` flag is shorthand for `--output json=<path>`.

## JSON

JSON is the default artifact format for CI comparison and machine-readable
run storage.

```console
$ rampa run load_test.py --out results.json
```

The file stores buffered samples. When the runner has a final metric
snapshot, it also writes summary metrics and threshold results.

## CSV

One row per sample. Tag keys become columns.

```console
$ rampa run load_test.py --output csv=metrics.csv
```

Output:

```
timestamp,metric,value,method,scenario,status
1716691200,http_reqs,1.0,GET,smoke,200
1716691201,http_req_duration,45.2,GET,smoke,200
```

## InfluxDB

Pushes samples as [line protocol](https://docs.influxdata.com/influxdb/v2/reference/syntax/line-protocol/) over HTTP.

```console
$ rampa run load_test.py \
  --output influxdb=http://localhost:8086/api/v2/write?org=myorg&bucket=rampa
```

Each sample becomes one line:

```
http_req_duration,method=GET,scenario=smoke value=45.2 1716691200000000000
```

Tags map to InfluxDB tags, the sample value maps to the `value` field,
and the monotonic nanosecond timestamp maps to the InfluxDB timestamp.

## Prometheus

Pushes metrics to Prometheus via the remote write API. Uses hand-crafted
protobuf v1 encoding with snappy compression (falls back to gzip if
`python-snappy` is not installed).

```console
$ rampa run load_test.py \
  --output prometheus=http://localhost:9090/api/v1/write
```

Each sample becomes a Prometheus TimeSeries with `__name__` set to the
metric name and sample tags as labels. Feeds Grafana dashboards directly.

Install `python-snappy` for optimal compression:

```console
$ uv add python-snappy
```

## OpenTelemetry

Exports metrics via OTLP/HTTP+JSON to any OpenTelemetry-compatible
collector (Grafana Alloy, OTEL Collector, Jaeger, etc.). Zero additional
dependencies.

```console
$ rampa run load_test.py --output otel=http://localhost:4318
```

The `/v1/metrics` path is appended automatically. Uses the JSON wire
format (proto3 standard JSON mapping) — no protobuf compiler needed.

## GitHub Actions

GitHub Actions output is for workflow presentation: threshold annotations
and `$GITHUB_STEP_SUMMARY` content. Keep JSON or CSV enabled when the run
also needs a downloadable artifact or a baseline for later comparison.

## Webhook

POST sample batches as JSON to any HTTP endpoint.

```console
$ rampa run load_test.py --output webhook=https://example.com/hook
```

Payload shape:

```json
{
  "samples": [
    {"metric": "http_reqs", "value": 1.0, "timestamp": 1716691200, "tags": {"method": "GET"}}
  ]
}
```

## Programmatic usage

```python
from rampa.outputs import get_output

csv_out = get_output("csv", "results.csv")
influx_out = get_output("influxdb", "http://localhost:8086/api/v2/write")
```

All outputs implement the {class}`~rampa.output.Output` protocol:
`start()`, `add_samples(batch)`, `stop(error)`.
