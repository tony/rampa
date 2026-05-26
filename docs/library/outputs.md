(outputs)=

# Output backends

rampa ships metric samples to output backends during and after a test run.
Use `--output` to send results to multiple destinations simultaneously.

## Built-in backends

| Backend | Destination | Dependencies |
|---------|------------|-------------|
| `console` | Terminal summary (default) | None |
| `json` | JSON file | None |
| `csv` | CSV file | None |
| `influxdb` | InfluxDB HTTP API | aiohttp (included) |
| `webhook` | Any HTTP endpoint | aiohttp (included) |

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
