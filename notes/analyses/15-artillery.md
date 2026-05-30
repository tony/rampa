# artillery — structural analysis

**Classification:** Node · event-loop (libuv) concurrency · **open-loop** arrival scheduling ·
declarative YAML + JS hooks · built-in distribution.
Pinned at [`artilleryio/artillery@artillery-2.0.32`](https://github.com/artilleryio/artillery/tree/artillery-2.0.32).

## Execution engine

A single `runner` drives all VUs on one Node event loop; each arrival calls `runScenario`, and VUs
progress through async callbacks interleaved on that loop. Per-loop CPU (templating, capture, JSON
parse) is the ceiling — CPU-bound work on one VU stalls every other — so artillery raises throughput
by adding worker threads/processes rather than per-loop concurrency.
→ [`packages/core/lib/runner.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/runner.js)

## Scheduling & pacing

Open-loop. The phaser turns `config.phases` into `arrival` events: `arrivalRate`/`rampTo`/
`arrivalCount`/`pause` fire N arrivals per second independent of in-flight count; ramps interpolate
over one-second windows; `maxVusers` bounds runaway concurrency. Load *shape* (phaser) is separated
from load *content* (runner).
→ [`packages/core/lib/phases.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/phases.js)

## Request/result data structure & metric data structure

The SSMS (statistical summary) module records metrics as **DDSketch** histograms (1% relative
accuracy, via `@artilleryio/sketches-js`) bucketed into time-normalized "periods", alongside counters
(`vusers.created/completed/failed`, `http.codes.*`) and rates. `summary`/`histogram`/`counter` are
emitted inline per request, but the heavy merge/serialize happens at period boundaries, off the hot
path. DDSketch is chosen for bounded-error percentiles *and* lossless mergeability.
→ [`packages/core/lib/ssms.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/ssms.js)

## Distributed / aggregation

Default platform runs the engine in worker threads; `distribute`/`multiply` and AWS Lambda/Fargate +
Azure ACI scale out, all emitting the *same* launcher event stream regardless of backend. The
launcher buffers per-worker periods by timestamp and emits a merged period once all workers report —
or after a timeout, so a straggler degrades liveness, not correctness. `mergeBuckets` recombines
DDSketches losslessly, so fleet-wide percentiles are computed after merge, never averaged.
→ [`packages/artillery/lib/platform/local/worker.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/artillery/lib/platform/local/worker.js)

## Scenario / user API

Declarative YAML: weighted `scenarios`, each a `flow` of steps (HTTP requests, `think`, `loop`,
`parallel`, `function`), with `capture` (extract into context) and `expect` (per-request assertions).
Each protocol is a separate engine behind the runner; the HTTP engine is one of several sibling engine
packages. Post-aggregate SLO thresholds are the `ensure` plugin (filtrex expressions → exit code).
→ [`packages/core/lib/engine_http.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/engine_http.js),
[`packages/artillery-plugin-ensure/index.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/artillery-plugin-ensure/index.js)

## Source basis

Cross-checked against pre-existing architecture-study notes and the pinned public source links
above.
