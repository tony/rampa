(executors)=

# Executors

Executors control how iterations are scheduled — how many virtual
users run, for how long, and at what rate. rampa provides six executor
types matching k6's scheduling vocabulary.

## Which executor should I use?

| I want to... | Executor | Model |
|--------------|----------|-------|
| Run N users for a fixed duration | `constant-vus` | Closed |
| Ramp users up and down | `ramping-vus` | Closed |
| Run exactly N total iterations | `shared-iterations` | Closed |
| Run N iterations per user | `per-vu-iterations` | Closed |
| Maintain a fixed request rate | `constant-arrival-rate` | Open |
| Ramp request rate up and down | `ramping-arrival-rate` | Open |

**Closed model** — each VU waits for the previous iteration to finish
before starting the next. The system under test controls the effective
rate. Use this when you want to simulate a fixed number of concurrent
users.

**Open model** — iterations start at a fixed rate regardless of
response time. If the system slows down, VUs pile up. Use this when
you want to measure behavior under a specific request rate. If VU
capacity is exhausted, the iteration is counted as `dropped_iterations`.

## constant-vus

Run a fixed number of VUs for a duration.

```python
@rampa.scenario(executor="constant-vus", vus=10, duration="30s")
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```

## ramping-vus

Linearly interpolate VU count between stages.

```python
@rampa.scenario(
    executor="ramping-vus",
    stages=[
        rampa.Stage(duration="30s", target=50),
        rampa.Stage(duration="1m", target=100),
        rampa.Stage(duration="30s", target=0),
    ],
)
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```

## shared-iterations

N VUs share a pool of M total iterations.

```python
@rampa.scenario(
    executor="shared-iterations",
    vus=10,
    iterations=1000,
)
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```

## per-vu-iterations

Each VU runs exactly N iterations independently.

```python
@rampa.scenario(
    executor="per-vu-iterations",
    vus=10,
    iterations=100,
)
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```

## constant-arrival-rate

Maintain a fixed request rate. Iterations that cannot start (all VUs
busy) are counted as `dropped_iterations`.

```python
@rampa.scenario(
    executor="constant-arrival-rate",
    rate=100,
    duration="1m",
    pre_allocated_vus=10,
    max_vus=50,
)
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```

## ramping-arrival-rate

Ramp the request rate linearly through stages.

```python
@rampa.scenario(
    executor="ramping-arrival-rate",
    stages=[
        rampa.Stage(duration="30s", target=50),
        rampa.Stage(duration="1m", target=200),
        rampa.Stage(duration="30s", target=0),
    ],
    pre_allocated_vus=10,
    max_vus=100,
)
async def default(worker: rampa.Worker) -> None:
    await worker.http.get("https://api.example.com/data")
```
