# ADR 008: Scenario and Plan API

Status: Proposed
Date: 2026-05-30

## Context

ADR 007 fixed rampa's direction — one contract surface, progressively disclosed across
single-process, multi-process, and distributed scale, honest about what it measures, Python-first
with optional acceleration — and deferred every mechanism to follow-up ADRs. This ADR decides the
first of those mechanisms: the **authoring surface**. It is the API a user writes against in a
script, a test, or a CI job, and the typed object that surface compiles into.

The authoring surface must be settled first because every later contract reads from it. The
scheduling model (ADR 010), the metric engine (ADR 011), and the scale and remote protocol
(ADR 012) all consume whatever the authoring layer produces. If the API is designed for the
single-process happy path alone, those later ADRs inherit a shape they must bend. The discipline
here is the reverse: decide a small, honest authoring contract that the later ADRs extend without
rework.

This ADR is written with greenfield latitude. It supersedes the current executor-string
configuration (`ScenarioConfig(executor="constant-vus", ...)`) and the `Worker` authoring object
as the *primary* surface. It preserves the strongest existing seam — the headless engine and run
controller split in `src/rampa/engine.py`, which already separates execution from presentation for
CLI, TUI, MCP, pytest, and CI frontends. The greenfield change is to the surface, not to that
separation.

Two existing ADRs bound this one. ADR 003 makes measurement semantics public behavior: scheduled
start, actual start, completion, timeout, cancellation, retry, and failure classification cannot be
silently dropped or reshaped. ADR 007 names the scenario API (aspiration 4) and pass/fail as a
first-class product (aspiration 5) as the capabilities this surface serves.

## Decision

rampa adopts a layered authoring surface that progressively discloses structure, compiling every
entry point into one immutable, serializable `Plan`. The simple path stays a few lines; the
distributed and remote paths reuse the same `Plan` and the same metric vocabulary.

### Progressive disclosure

The surface has three layers. A user climbs only as far as the task requires.

Layer 1 — script. A decorated async function and a single call:

```python
import rampa

@rampa.scenario(rampa.vus(10, duration="30s"))
async def smoke(vu: rampa.VU) -> None:
    res = await vu.http.get("/health")
    vu.check(res, {"status is 200": lambda r: r.status == 200})

result = await rampa.run(smoke, target="https://example.com")
```

Layer 2 — explicit `Plan`, for CI and library use:

```python
plan = rampa.Plan(
    target="https://example.com",
    scenarios=[
        rampa.Scenario(checkout, schedule=rampa.arrivals(rate=100, per="1s", duration="5m")),
    ],
    thresholds=[
        rampa.metric("http_req_duration").p(95) < rampa.ms(500),
        rampa.metric("http_req_failed").rate < 0.01,
    ],
    outputs=[rampa.json("results.json"), rampa.console()],
)
result = await rampa.run(plan)
```

Layer 3 — scale is one argument; the `Plan` does not change:

```python
result = await rampa.run(plan, on=rampa.local())
result = await rampa.run(plan, on=rampa.distributed(coordinator="wss://...", workers=20))
```

The same `Plan` is the unit for the CLI, the pytest plugin, the MCP server, local runs, and later
remote runs. Frontends differ in presentation and exit behavior, never in the contract they consume.

### The scenario and the VU authoring object

A scenario is an ordinary async Python function that receives an explicit per-iteration object. The
object is passed in, not drawn from ambient context, so a scenario can be unit-tested by calling it
with a stand-in object — no engine, event loop fixture, or framework bootstrap required.

That object is named `VU` (virtual user). The current `Worker` name is retained only as an internal
or compatibility alias. The rename removes a real collision: in any distributed design "worker"
means a node or process, and the per-iteration authoring object must not share that word. `VU` is
also standard load-testing vocabulary and reads correctly in examples.

The `VU` surface stays minimal: protocol clients (`vu.http`, `vu.ws`, `vu.grpc`), the check helper,
and custom-metric emitters (`vu.counter`, `vu.gauge`, `vu.trend`). It carries immutable execution
identity and any setup data. It owns no scheduling logic; the executor owns pacing.

### Schedules are typed constructors, not executor strings

The primary schedule vocabulary is a small set of typed constructors that name intent in Python.
Executor strings (`"constant-vus"`, `"ramping-arrival-rate"`) are retained only as aliases for
interoperability, not as the documented surface. rampa should read as Python, not as another tool's
configuration dialect.

| Constructor | Loop model | Intent |
|---|---|---|
| `vus(n, duration)` | closed | N concurrent users for a duration |
| `ramping_vus(stages)` | closed | linear VU ramp between stage targets |
| `per_vu_iterations(n, vus)` | closed | each VU runs exactly N iterations |
| `shared_iterations(total, vus)` | closed | N users share a total iteration budget |
| `arrivals(rate, per, duration, max_vus)` | open | requests fire on a schedule; overflow is recorded as dropped, not slowed |
| `ramping_arrivals(stages, ...)` | open | arrival rate interpolated between stage targets |

Closed-loop and open-loop are named distinctly because they differ in measurement honesty, not just
configuration. The internals of pacing — the pure-function pacer, drift handling, scheduled-versus-
actual accounting — are deferred to ADR 010; this ADR fixes only the public constructors and which
loop model each names.

### The Plan is the immutable, serializable contract boundary

`Plan` is the single typed object every entry point compiles into. It carries the target,
scenarios, thresholds, and outputs. It is immutable and its declarative content is serializable, so
it can travel to a remote worker or be recorded as a run artifact.

A scenario's *schedule, thresholds, and options* are always serializable. A scenario's *behavior* is
either an in-process Python callable (local execution) or shipped as a code archive (remote
execution); a declarative behavior subset that travels without code is anticipated but is the
subject of the scenario/native-execution ADR, not this one. Arbitrary Python always runs in Python,
per ADR 003.

### Checks are facts; thresholds are policy

Per-iteration checks return facts about a single response; thresholds evaluate aggregate policy and
drive the CI exit code. Both are first-class, because an API user needs a pass/fail verdict, not
only a summary.

The primary check form is a mapping of named predicates. It binds response, predicate, check name,
and the resulting metric tags in one expression, and each named predicate is independently testable
and independently reportable (a threshold can target a single named check):

```python
vu.check(res, {
    "status is 200": lambda r: r.status == 200,
    "has body": lambda r: len(r.body) > 0,
})
```

A terse single-named-boolean form is supported as sugar but is not the only documented path:

```python
vu.check("status is 200", res.status == 200)
```

The threshold expression language is named here only as a surface (`rampa.metric(...).p(95) <
rampa.ms(500)`); its grammar and evaluation belong to the checks-and-thresholds work under ADR 011.

### The scale seam is a streaming, controllable driver

Scale is introduced through an `ExecutionDriver` seam. It is named here and its lifecycle shape is
fixed; its modes, partitioning, and wire protocol are deferred to ADR 012.

The driver is **not** a synchronous compute-and-return contract. A load run is long-lived,
observable, and cancellable, so the driver is defined around a streaming, controllable lifecycle
that generalizes the existing `RunController`:

```python
handle = await driver.start(plan, context)   # begins the run, returns a control surface
async for event in handle.events():           # live phase, snapshot, threshold events
    ...
snapshot = handle.snapshot()                   # latest metric snapshot on demand
await handle.stop(reason)                       # cooperative cancellation
result = await handle.wait()                    # final RunResult
```

`LocalDriver`, `ProcessDriver`, `DistributedDriver`, and `RemoteDriver` satisfy this one lifecycle.
The precedent worth borrowing is the *swappability* of a single execution interface (as in Dask's
scheduler family), not its synchronous signature. The principle that makes swappability trustworthy
is that every driver feeds the *same* metric path, so local and distributed runs produce the same
result shape — the comparable-across-scale guarantee of ADR 007.

## Measurement assumptions

This section names the measurement contract the authoring surface assumes, so later ADRs are not
forced to bend this API. It deliberately does not fix fields.

- **Operation attempt record.** Protocol engines will emit a rich, transient *operation attempt
  record* at the measurement boundary, projected immediately into metric observations and then
  discarded — never retained per request. The name is "operation attempt," not "request," because
  retries, redirects, WebSocket messages, gRPC stream frames, and user-defined protocol calls do not
  map cleanly to one HTTP request. The record is anticipated to carry at least a logical operation
  identity, an attempt index, scheduled start, actual start, operation start, end, outcome, error
  class, timing phases, bytes, and tags. The exact fields, the projection rules, and the
  failure taxonomy are defined by ADR 009, not here. The current flat `Sample` in
  `src/rampa/_types.py` remains valid as a metric observation and as the projection target, but is
  too lossy to be what protocol engines emit.

- **Run-relative, period-keyed summaries.** Distributed aggregation ships mergeable summaries keyed
  by run-relative period, not raw samples and not absolute timestamps. Monotonic clocks are not
  comparable across hosts: preserving a worker's monotonic timestamp at a coordinator is meaningless,
  and re-stamping at the coordinator discards when the work happened on the worker. Worker-local
  projection into run-relative periods avoids both. The default for final aggregate results is
  worker-relative periods. Globally phased open-loop runs additionally require a start barrier and a
  declared clock-skew tolerance in the control plane; live time-aligned charts require an explicit
  period anchor model. These mechanisms belong to ADR 012.

- **Reduce after merge.** Percentiles are computed on a merged mergeable summary, never by averaging
  precomputed percentiles. This is a hard constraint on ADR 011, recorded here because the authoring
  surface must not promise an aggregate the metric engine cannot honestly merge.

## Scope

This ADR decides the authoring surface and the `Plan` shape: the scenario function signature, the
`VU` object and its name, the typed schedule constructors and which loop model each names, the
immutable serializable `Plan`, the check forms, and the existence and lifecycle shape of the
`ExecutionDriver` seam.

It does not decide: the operation attempt record's fields or projection rules (ADR 009); the pacer,
drift, and scheduled-versus-actual mechanics (ADR 010); the metric data structures, merge
algorithm, or threshold grammar (ADR 011); the scale modes, partitioning, capability negotiation,
start barrier, archives, and wire protocol (ADR 012); and any native boundary placement (ADR 002,
ADR 003).

## Deferred to follow-up ADRs

The authoring surface hands off to a sequence of narrow ADRs, ordered so the measurement contract is
fixed before the worker machinery hardens:

- **ADR 009 — operation attempt record and event model.** The rich transient record, its fields,
  projection to metric observations, and failure taxonomy.
- **ADR 010 — execution and scheduling model.** The pure-function pacer, open and closed loops,
  drift handling, dropped and late accounting, scheduled-versus-actual recording.
- **ADR 011 — metric engine and storage.** Bounded, mergeable summaries; the threshold grammar and
  evaluation; reduce-after-merge.
- **ADR 012 — scale modes and control plane.** `ExecutionDriver` modes (local, process, distributed,
  remote), deterministic partitioning, capability negotiation, start barrier, run-relative time
  model, archives, and artifacts.

## Consequences

### Positive

- The simple path stays small: a decorated async function and one call, with no scale machinery in
  view.
- One `Plan` serves every frontend and every scale, which is the structural form of ADR 007's
  comparable-results-across-scale guarantee.
- Scenarios are plain callables over an explicit `VU`, so they are unit-testable without the engine.
- Naming the operation attempt record and the run-relative summary model now — without fixing their
  fields — keeps ADR 008 from designing an API that ADR 009 and ADR 011 would have to bend.
- The `VU` rename removes the `worker` collision before distributed mode introduces it.

### Tradeoffs

- The greenfield surface supersedes the current executor-string configuration and the `Worker` name
  as the primary API. Existing scripts written against those move to the new surface, with the
  executor-string aliases easing interoperation.
- Fixing the `ExecutionDriver` lifecycle now constrains ADR 012 to a streaming, controllable shape.
  This is intended: a synchronous compute-and-return driver could not support live snapshots,
  cancellation, or distributed control.

### Risks

- **Averaged aggregates.** The AWS distributed-load-testing solution is a strong control-plane
  exemplar — archive, regional compatibility, stabilization, start markers, completion markers,
  artifacts — but its results parser averages aggregate fields, and its percentile keys are run
  through the same arithmetic mean (`createFinalResults` in
  `source/results-parser/lib/parser/index.js`). Averaging precomputed percentiles is exactly the
  reduction rampa must not adopt. The mitigation is the reduce-after-merge constraint named in
  Measurement assumptions and bound on ADR 011, and treating AWS DLT as a control-plane model only,
  never a metric model.
- **Surface drift before the contract is whole.** The authoring API is decided before the event,
  scheduler, metric, and scale ADRs. The mitigation is the Measurement assumptions section, which
  names each downstream contract this surface depends on so the dependency is explicit rather than
  discovered later.

## Relationship to ADR 003 and ADR 007

ADR 007 names the scenario API (aspiration 4) and pass/fail as a first-class product (aspiration 5);
this ADR is the first concrete realization of both, and it opens the follow-up ADR sequence ADR 007
anticipated. ADR 003 bounds the surface: the authoring API may not expose or imply any aggregate or
timing semantics that the measurement layer cannot honestly preserve, and arbitrary Python scenarios
run in Python.

## Final position

rampa's authoring surface is a small, Pythonic, testable contract: an async scenario over an
explicit `VU`, typed schedule constructors, named checks, and one immutable, serializable `Plan`
that every frontend and every scale consumes unchanged. Scale enters through a streaming,
controllable `ExecutionDriver` seam whose modes are deferred. The surface is decided first and kept
honest by naming — not yet defining — the operation attempt record and the run-relative, merge-after-
reduce measurement model that the following ADRs will specify.
