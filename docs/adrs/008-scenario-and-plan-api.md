# ADR 008: Scenario and Plan API

Status: Proposed
Date: 2026-05-30

## Context

ADR 007 fixed rampa's direction — one contract surface, progressively disclosed across
single-process, multi-process, and distributed scale, honest about what it measures, Python-first
with optional acceleration — and deferred every mechanism to follow-up ADRs. This ADR decides the
first of those mechanisms: the **authoring surface**. It is the API a user writes against in a
script, a test, or a CI job, and the typed object that surface compiles into.

The authoring surface must be settled first because every later contract reads from it. The event
model (ADR 009), the scheduling model (ADR 010), the protocol engines (ADR 011), the metric engine
(ADR 012), and the scale and remote protocol (ADR 013) all consume whatever the authoring layer
produces. If the API is designed for the single-process happy path alone, those later ADRs inherit
a shape they must bend. The discipline here is the reverse: decide a small, honest authoring
contract that the later ADRs extend without rework.

This ADR is written with greenfield latitude. It supersedes the current executor-string
configuration (`ScenarioConfig(executor="constant-vus", ...)`) and the per-iteration `Worker`
object as the *primary* surface. It preserves the strongest existing seam — the headless engine and
run controller split in `src/rampa/engine.py`, which already separates execution from presentation
for CLI, TUI, MCP, pytest, and CI frontends. The greenfield change is to the surface, not to that
separation.

Two existing ADRs bound this one. ADR 003 makes measurement semantics public behavior: scheduled
start, actual start, completion, timeout, cancellation, retry, and failure classification cannot be
silently dropped or reshaped. ADR 007 names the scenario API (aspiration 4) and pass/fail as a
first-class product (aspiration 5) as the capabilities this surface serves.

## Decision

rampa adopts a layered authoring surface that progressively discloses structure, compiling every
entry point into one immutable, normalized `Plan`. The simple path stays a few lines and runs as an
ordinary script; the distributed and remote paths reuse the same `Plan` and the same metric
vocabulary. A scenario describes *behavior*; a schedule describes *how hard to run it*; the two are
bound at run time, not fused into the scenario's identity.

### Progressive disclosure

The surface has three layers. A user climbs only as far as the task requires.

Progressive disclosure is a guardrail, not just an ordering for examples. Beginner-facing APIs use
the shortest call that still states intent: `rampa.run(...)` for load scenarios, browser profiling
shortcuts from ADR 014 for frontend probes, and `rampa.bench.run(...)` from ADR 015 for
project-owned benchmark suites. Those calls all normalize into `Plan`, operation-attempt,
metric-summary, adapter, and driver contracts. The lower contracts must not force simple examples
to begin with coordinators, event records, worker protocols, or adapter descriptors.

Layer 1 — script. A behavior, and one call that names the schedule:

```python
import rampa

@rampa.scenario
async def smoke(vu: rampa.VU) -> None:
    res = await vu.http.get("/health")
    vu.check("status is 200", res.status == 200, subject=res)

result = rampa.run(
    smoke,
    base_url="https://example.com",
    schedule=rampa.vus(10, duration="30s"),
)
```

`rampa.run(...)` is synchronous: it owns the event loop and returns a `RunResult`, so the example is
a complete script. Inside an existing event loop, `await rampa.arun(...)` is the async equivalent.

Layer 2 — explicit `Plan`, for CI and library use:

```python
plan = rampa.Plan(
    base_url="https://example.com",
    scenarios=[
        rampa.Scenario(
            name="checkout",
            behavior=rampa.python_callable(checkout),
            schedule=rampa.arrivals(rate=100, per="1s", duration="5m", max_vus=500),
        ),
    ],
    thresholds=[
        rampa.metric("http.duration").p(95) < rampa.ms(500),
        rampa.metric("http.failed").rate < 0.01,
    ],
    outputs=[rampa.json("results.json"), rampa.console()],
)
result = rampa.run(plan)
```

Layer 3 — scale is one argument; the `Plan` does not change:

```python
result = rampa.run(plan, scale=rampa.local())
result = rampa.run(plan, scale=rampa.distributed(coordinator="wss://...", workers=20))
```

The same `Plan` is the unit for the CLI, the pytest plugin, the MCP server, local runs, and later
remote runs. Frontends differ in presentation and exit behavior, never in the contract they consume.

### One scenario object, schedule bound at run time

`@rampa.scenario` produces a `rampa.Scenario`. A decorated function therefore drops straight into a
`Plan` (`Plan(scenarios=[smoke])`), and the decorator and the `Scenario` constructor are the same
object underneath, not two mechanisms.

A schedule is not part of a scenario's identity. The same behavior must be runnable as a one-VU
smoke check, a hundred-arrival CI gate, an overnight soak, and a distributed stress run without
redefining or redecorating the function. Schedules therefore bind at run time. A decorator may carry
a *default* schedule as a convenience, but it is metadata, not identity:

```python
@rampa.scenario(default_schedule=rampa.vus(10, duration="30s"))
async def smoke(vu: rampa.VU) -> None:
    ...
```

Schedule precedence is explicit, as three rules. A `Scenario(schedule=...)` takes precedence over a
`run(..., schedule=...)` argument. A decorator `default_schedule` is used only when neither a
`Scenario` schedule nor a `run` schedule is given. Supplying both a decorator `default_schedule` and
an explicit `Scenario(schedule=...)` for the same scenario is a normalization error, not a silent
override.

A top-level `run(..., schedule=...)` applies only when the input is a bare scenario or a
single-scenario `Plan` whose scenario has no schedule. Supplying a top-level run schedule for a
multi-scenario `Plan` is a normalization error; each scenario must carry its own schedule so load
mixes remain explicit.

### The scenario and the VU runtime handle

A scenario is an ordinary async Python function that receives an explicit `VU` runtime handle. The
handle is passed in, not drawn from ambient context, so a scenario can be unit-tested by calling it
with a stand-in handle — no engine, event-loop fixture, or framework bootstrap required.

The object is named `VU` (virtual user). The current `Worker` name is retained only as an internal
or compatibility alias. The rename removes a real collision: in any distributed design "worker"
means a node or process, and the per-iteration authoring object must not share that word.

**A `VU` represents a virtual user, not a single iteration.** Its state lifetime is the virtual
user, and this differs by loop model:

- In **closed-loop** and finite schedules (`vus`, `ramping_vus`, `per_vu_iterations`,
  `shared_iterations`, `repeat`), a VU persists across its iterations. Mutable VU-scoped state — an
  auth token fetched once, a cookie jar, a protocol session — lives on the VU and survives between
  that VU's iterations. This is the canonical pattern: authenticate once, reuse the credential for
  every later iteration. A once-per-VU initialization, distinct from once-per-run setup, is
  anticipated for this; its exact form is defined by ADR 010.
- In **open-loop** schedules (`arrivals`, `ramping_arrivals`), the scheduler starts iterations on a
  clock independent of whether earlier iterations have finished. Whether a started iteration gets a
  fresh VU or borrows one from a pool, and the state-reuse and isolation rules when arrivals outpace
  completion, are defined by ADR 010. The authoring contract fixes only that VU-scoped state has VU
  lifetime, never silently iteration lifetime.

The VU carries immutable execution identity (a stable VU id, the scenario name, the iteration
index), read-only run-global `setup_data`, and mutable VU-scoped state. The VU surface stays
minimal: protocol clients (`vu.http`, `vu.ws`, `vu.grpc`), the check helper, and custom-metric
emitters (`vu.counter`, `vu.gauge`, `vu.trend`). It owns no scheduling logic; the executor owns
pacing.

rampa does not model intra-VU weighted task selection. A scenario is one behavior; a load mix is
expressed as separate scenarios with independent schedules in one `Plan`, and a scenario that needs
internal branching does so in plain Python and names its operations. This keeps scenario identity,
scheduling, and metric attribution aligned.

### Schedules are typed constructors, not executor strings

The primary schedule vocabulary is a small set of typed constructors that name intent in Python.
Executor strings (`"constant-vus"`, `"ramping-arrival-rate"`) are retained only as aliases for
interoperability, not as the documented surface. rampa should read as Python, not as another tool's
configuration dialect.

| Constructor | Loop model | Intent |
|---|---|---|
| `vus(n, duration)` | closed | N concurrent virtual users for a duration |
| `ramping_vus(stages)` | closed | linear VU ramp between stage targets |
| `per_vu_iterations(n, vus)` | closed | each VU runs exactly N iterations |
| `shared_iterations(total, vus)` | closed | N VUs share a total iteration budget |
| `repeat(n)` | finite diagnostic | run exactly N iterations for smoke checks, profiling, browser probes, and benchmarks |
| `arrivals(rate, per, duration, max_vus)` | open | scenario iterations start on a schedule; overflow is recorded as dropped, not slowed |
| `ramping_arrivals(stages, ...)` | open | scenario-iteration arrival rate interpolated between stage targets |

Open-loop schedules start **scenario iterations**, not requests: one iteration may issue several HTTP
calls, WebSocket messages, sleeps, and checks. Closed-loop and open-loop are named distinctly because
they differ in measurement honesty, not just configuration. The pacing internals — the pure-function
pacer, drift handling, scheduled-versus-actual accounting — are deferred to ADR 010; this ADR fixes
only the public constructors and which loop model each names.

`repeat(n)` is deliberately not an offered-load model. It is the small finite schedule for examples,
smoke checks, profile captures, browser first-paint probes, and benchmark targets that need a
repeat count without implying VU concurrency or arrival-rate claims. ADR 010 defines its timing and
reporting semantics.

### The Plan is the immutable, normalized contract boundary

`Plan` is the single typed object every entry point compiles into. It carries the base URL (and,
later, general protocol defaults), scenarios, thresholds, and outputs. It is immutable after
normalization; its *declarative* fields are serializable, so a plan can be recorded as a run
artifact or moved to a remote worker.

Scenario behavior is represented by a **behavior reference**, not a bare object embedded in a
serializable structure. The supported forms depend on the execution driver:

- a **local callable** (`rampa.python_callable(checkout)`) — valid for in-process and on-host
  multi-process execution;
- an **import path** (`rampa.import_path("tests.load:checkout")`) — valid for remote Python
  execution where the worker can import the module;
- an **archive reference** (a code bundle plus entrypoint) — valid for remote execution that ships
  the code;
- a future **declarative or native behavior subset** — the subject of the scenario/native-execution
  work, not this ADR.

A driver validates each behavior reference's form before a run starts; an unsupported form is
rejected up front, never silently degraded. Arbitrary Python always runs in Python, per ADR 003.

Normalization assigns each scenario a stable id and rejects duplicate scenario names. Stable ids are
what metrics, artifacts, threshold selectors, and distributed partitioning key on.

### Checks are facts; thresholds are policy

Per-iteration checks return facts about a single operation result: the `subject` passed to the
check. Thresholds evaluate aggregate policy and drive the CI exit code. Both are first-class,
because an API user needs a pass/fail verdict, not only a summary.

The primary check form is a named boolean. It reads cleanly for the common case, evaluates eagerly
in user code, types well, and stays out of the hot path:

```python
vu.check("status is 200", res.status == 200, subject=res)
vu.check("has body", len(res.body) > 0, subject=res)
```

A raising expression in a named-boolean check is a scenario error, not a check failure, because the
framework never sees the predicate. When framework-managed evaluation is wanted — a predicate that
raises should be classified as a failed check rather than aborting the iteration — or when many
checks share a subject, the batch form takes a mapping of named predicates:

```python
vu.check_all(res, {
    "status is 200": lambda r: r.status == 200,
    "has body": lambda r: len(r.body) > 0,
})
```

Both forms emit per-check metrics under stable, named check identities, so a threshold can target a
single named check. Protocol-specific check ergonomics (for example `res.expect.status(200)`) are a
protocol-engine concern under ADR 011. The threshold expression language is named here only as a
surface (`rampa.metric(...).p(95) < rampa.ms(500)`); its grammar and evaluation belong to ADR 012.

Metric names use rampa's own dotted namespace, not another tool's: `http.duration`, `http.failed`,
`http.bytes_in`, `http.bytes_out`, `checks.passed`, `checks.failed`, `iterations.started`,
`iterations.completed`, `iterations.dropped`, `iterations.late`. Derived ratios and rates, such as
an HTTP failure rate or a check pass ratio, are projections defined by ADR 012's threshold grammar;
they are not separate primary metric names in this ADR. Foreign metric names are accepted only as
import or interop aliases, never as the documented primary names.

### Base URL and protocol defaults

`base_url` on a `Plan` (or on `run(...)`) is a **default base for relative paths**: a scenario may
write `vu.http.get("/health")` and have it resolve against the base. Absolute URLs remain valid and
ignore the base, and a scenario may target more than one host. `base_url` is HTTP sugar over a more
general protocol-defaults structure; the general form (per-protocol defaults, per-scenario override
precedence) is the subject of the protocol-engine work under ADR 011. The authoring contract fixes
only that `base_url` is a default, not a hard single-host binding.

### The scale seam is a streaming, controllable driver

Scale is introduced through an `ExecutionDriver` seam, selected by the public `scale=` argument
(`rampa.local()`, `rampa.distributed(...)`). The seam is named here and its lifecycle shape is
fixed; its modes, partitioning, and wire protocol are deferred to ADR 013.

A load run is long-lived, observable, and cancellable, so the driver is defined around a streaming,
controllable lifecycle that generalizes the existing `RunController` — not a synchronous
compute-and-return contract:

```python
handle = await rampa.start(plan, scale=rampa.local())   # begins the run, returns a control surface
async for event in handle.events():                       # live phase, snapshot, threshold events
    ...
snapshot = handle.snapshot()                               # latest metric snapshot on demand
await handle.stop("operator requested stop")               # cooperative cancellation
result = await handle.wait()                                # final RunResult
```

`rampa.run(...)` and `rampa.arun(...)` are convenience wrappers: they start the selected driver,
connect the configured outputs, wait for completion, and return a `RunResult`. `rampa.start(...)`
exposes the streaming, controllable lifecycle directly. `LocalDriver`, `ProcessDriver`,
`DistributedDriver`, and `RemoteDriver` satisfy this one lifecycle. The precedent worth borrowing is
the *swappability* of a single execution interface, not its synchronous signature. The principle
that makes swappability trustworthy is that every driver feeds the *same* metric path, so local and
distributed runs produce the same result shape — the comparable-across-scale guarantee of ADR 007.
`workers=20` above is illustrative; the scale
vocabulary (segments, regions, worker capabilities, remote pools) is richer and belongs to ADR 013,
so `workers` is not treated as the only scale unit.

## Measurement assumptions

This section names the measurement contract the authoring surface assumes, so later ADRs are not
forced to bend this API. It deliberately does not fix fields.

- **Operation attempt record.** Protocol engines will emit a rich, transient *operation attempt
  record* at the measurement boundary, projected into metric observations and mergeable summaries.
  The name is "operation attempt," not "request," because retries, redirects, WebSocket messages,
  gRPC stream frames, and user-defined protocol calls do not map cleanly to one HTTP request. The
  record is anticipated to carry at least a logical operation id, an attempt index, scheduled start,
  actual start, operation start, end, outcome, error class, timing phases, bytes, and tags. The exact
  fields, the projection rules, and the failure taxonomy are defined by ADR 009, not here. In the
  normal hot path the record is projected and then discarded; debug, trace, and failure-sampling
  modes may retain bounded or redacted attempt records explicitly (for example the slowest N, a
  sampled fraction, or failure exemplars), but raw per-attempt retention is not the default metric
  path. The current flat `Sample` in `src/rampa/_types.py` remains valid as a metric observation and
  as a projection target, but is too lossy to be what protocol engines emit.

- **Worker-local run-relative summaries.** Distributed aggregation ships mergeable summaries keyed by
  worker-local run-relative period, not raw samples and not absolute timestamps. Monotonic clocks are
  not comparable across hosts: preserving a worker's monotonic timestamp at a coordinator is
  meaningless, and re-stamping at the coordinator discards when the work happened on the worker.
  Final aggregate results merge all worker summaries and do not require globally aligned wall-clock
  periods — final correctness does not depend on pretending monotonic clocks are comparable.
  Time-aligned live charts, globally phased open-loop starts, and per-period cross-worker charts
  require an explicit period anchor model, a start barrier, and a declared clock-skew tolerance in
  the control plane. These mechanisms belong to ADR 013.

- **Reduce after merge.** Percentiles are computed on a merged mergeable summary, never by averaging
  precomputed percentiles. This is a hard constraint on ADR 012, recorded here because the authoring
  surface must not promise an aggregate the metric engine cannot honestly merge.

- **Stable check and metric identities.** Named checks and metric names are stable, addressable
  identifiers, because a threshold can target a single named check or metric. Their naming rules —
  permitted characters, uniqueness scope, normalization — constrain the threshold grammar and are
  fixed by ADR 012.

## Scope

This ADR decides the authoring surface and the `Plan` shape: the scenario function signature; the
`VU` runtime handle, its name, and its state-lifetime model (per virtual user, not per iteration);
the schedule-binds-at-run-time rule and precedence; the typed schedule constructors and which loop
model each names; the immutable, normalized `Plan` with serializable declarative fields and behavior
references; the named-boolean and batch check forms; the rampa metric namespace; `base_url`
semantics; and the existence, public argument (`scale=`), and lifecycle shape of the
`ExecutionDriver` seam.

It does not decide: the operation attempt record's fields or projection rules (ADR 009); the pacer,
drift, scheduled-versus-actual mechanics, and open-loop VU state-reuse and once-per-VU init (ADR
010); the protocol client engines and their per-operation surfaces (ADR 011); the metric data
structures, merge algorithm, and threshold grammar and evaluation (ADR 012); the scale modes,
partitioning, capability negotiation, start barrier, and wire protocol (ADR 013); and any native
boundary placement (ADR 002, ADR 003).

## Deferred to follow-up ADRs

The authoring surface hands off to a sequence of narrow ADRs, ordered so the measurement contract is
fixed before the worker machinery hardens. The numbering is indicative, consistent with ADR 007's
roadmap:

- **ADR 009 — operation attempt record and event model.** The rich transient record, its fields,
  projection to metric observations, and failure taxonomy.
- **ADR 010 — execution and scheduling model.** The pure-function pacer; open and closed loops;
  drift, dropped, and late accounting; scheduled-versus-actual recording; closed-loop VU persistence,
  the once-per-VU init, and open-loop VU state-reuse and isolation.
- **ADR 011 — protocol client engines.** HTTP, WebSocket, gRPC, and custom engines behind the
  `vu.http` / `vu.ws` / `vu.grpc` surfaces; operation naming; protocol-specific check ergonomics; the
  general protocol-defaults structure `base_url` is sugar over.
- **ADR 012 — metric engine and storage, and aggregate thresholds.** Bounded, mergeable summaries;
  reduce-after-merge; and the aggregate threshold expression grammar and evaluation. Named-check
  emission *semantics* are decided in this ADR; the aggregate threshold *language* lives in ADR 012.
  Derived projections such as `.rate` must be defined there with an explicit denominator, time
  window, failure classification, and distributed merge behavior.
- **ADR 013 — scale modes and control plane.** `ExecutionDriver` modes (local, process, distributed,
  remote); deterministic partitioning; capability negotiation; start barrier; run-relative time
  model; archives; and artifacts.

Outputs and exporters and the Rust acceleration map remain ADR 007 roadmap items beyond this
immediate sequence.

## Consequences

### Positive

- The simple path stays small and runs as an ordinary script: a behavior, a `run(...)` call naming
  the schedule, no scale machinery in view, no event-loop ceremony.
- A scenario is reusable across run profiles because the schedule is a run parameter, not part of the
  function's identity.
- One `Plan` serves every frontend and every scale, which is the structural form of ADR 007's
  comparable-results-across-scale guarantee.
- Scenarios are plain callables over an explicit `VU`, so they are unit-testable without the engine.
- The VU state-lifetime decision makes the authenticate-once pattern correct by construction in
  closed-loop and forces the open-loop reuse question into ADR 010 rather than leaving it ambiguous.
- Behavior references separate what is serializable (the declarative plan) from what a driver must be
  able to resolve (the behavior), so ADR 013 does not have to retrofit serialization semantics.
- Naming the operation attempt record, the worker-local run-relative summary model, and the stable
  check identities now — without fixing their fields or grammar — keeps ADR 008 from designing an API
  that ADR 009, ADR 012, or ADR 013 would have to bend.
- The `VU` rename removes the `worker` collision before distributed mode introduces it.

### Tradeoffs

- The greenfield surface supersedes the current executor-string configuration and the per-iteration
  `Worker` as the primary API. Existing scripts move to the new surface, with the executor-string and
  foreign-metric-name aliases easing interoperation.
- Making the VU persist across iterations in closed-loop is a behavior change from the current
  per-iteration `Worker`; the engine must now own per-VU lifetime and a once-per-VU init, specified
  in ADR 010.
- Fixing the `ExecutionDriver` lifecycle now constrains ADR 013 to a streaming, controllable shape.
  This is intended: a synchronous compute-and-return driver could not support live snapshots,
  cancellation, or distributed control.

### Risks

- **Averaged aggregates.** Distributed Load Testing on AWS (Apache-2.0) is a strong control-plane
  exemplar — archive, regional compatibility, stabilization, start markers, completion markers,
  artifacts — but its results parser averages aggregate fields, and its percentile keys fall through
  to the same arithmetic mean (the default branch of `createFinalResults` in
  [`source/results-parser/lib/parser/index.js`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/results-parser/lib/parser/index.js)).
  Averaging precomputed percentiles is exactly the reduction rampa must not adopt. The mitigation
  is the reduce-after-merge constraint named in Measurement assumptions and bound on ADR 012, and
  treating the AWS solution as a control-plane model only, never a metric model.
- **Surface drift before the contract is whole.** The authoring API is decided before the event,
  scheduler, protocol, metric, and scale ADRs. The mitigation is the Measurement assumptions section,
  which names each downstream contract this surface depends on so the dependency is explicit rather
  than discovered later.

## Relationship to ADR 003 and ADR 007

ADR 007 names the scenario API (aspiration 4) and pass/fail as a first-class product (aspiration 5);
this ADR is the first concrete realization of both, and it opens the follow-up ADR sequence ADR 007
anticipated. ADR 003 bounds the surface: the authoring API may not expose or imply any aggregate or
timing semantics that the measurement layer cannot honestly preserve, and arbitrary Python scenarios
run in Python.

## Final position

rampa's authoring surface is a small, Pythonic, testable contract: an async scenario over an explicit
`VU` virtual-user handle, typed schedule constructors bound at run time, named checks, and one
immutable, normalized `Plan` — declarative fields serializable, behavior carried by a reference — that
every frontend and every scale consumes unchanged. Scale enters through a streaming, controllable
`ExecutionDriver` seam selected by `scale=`, whose modes are deferred. The surface is decided first
and kept honest by naming — not yet defining — the operation attempt record and the run-relative,
reduce-after-merge measurement model that the following ADRs will specify.
