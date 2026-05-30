# jmeter — structural analysis

**Classification:** JVM · thread-per-VU concurrency · closed-loop scheduling (open model bolted on
later) · declarative XML test plan · built-in distribution.
Pinned at [`apache/jmeter@rel/v5.6.3`](https://github.com/apache/jmeter/tree/rel/v5.6.3).

## Execution engine

The canonical heavyweight: one JVM thread per virtual user. `StandardJMeterEngine` manages the
`ThreadGroup` lifecycle; each `ThreadGroup` spawns N `JMeterThread` runnables over a ramp-up window,
and each thread runs the plan in a blocking loop. Before the run, `TreeCloner` gives every thread a
**deep copy** of its subtree (a second per-VU memory multiplier on top of thread stacks). Concurrency
is bounded by thread stacks and context-switching, not by the target — the model rampa should not
copy at scale.
→ [`engine/StandardJMeterEngine.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/engine/StandardJMeterEngine.java),
[`threads/ThreadGroup.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/threads/ThreadGroup.java),
[`threads/AbstractThreadGroup.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/threads/AbstractThreadGroup.java)

## Scheduling & pacing

Closed-loop by default: the next sampler starts when the previous finishes, with timers adding
think-time delays — so under load the schedule drifts late and coordinated omission goes unmeasured.
Open scheduling was added later: `PreciseThroughputTimer` (Poisson arrivals) and the Kotlin
`OpenModelThreadGroup` express rate-shaped, declarative profiles the classic threads+ramp+loops model
cannot. That it had to be bolted on is the lesson to design arrival scheduling into the core.
→ [`threads/openmodel/OpenModelThreadGroup.kt`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/kotlin/org/apache/jmeter/threads/openmodel/OpenModelThreadGroup.kt)

## Request/result data structure

`SampleResult` is a fat telemetry object: response time, latency (TTFB), connect time, bytes
sent/received, status, success flag, start/end time, sub-results (embedded resources), and attached
assertion results.
→ [`samplers/SampleResult.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/samplers/SampleResult.java)

## Metric & percentile data structure

Two paths. Live: in-memory `StatCalculator` inside GUI visualizers (retains samples — the documented
memory/throughput killer; run non-GUI under load). Offline: a streaming consumer pipeline where
`PercentileAggregator` (over Apache Commons Math `DescriptiveStatistics`) and `StatisticsSummaryData`
compute percentiles one `Sample` at a time, with disk-spill for multi-GB result files.
`DescriptiveStatistics` retains the window for exact percentiles — an explicit memory/accuracy
trade-off.
→ [`report/processor/PercentileAggregator.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/report/processor/PercentileAggregator.java),
[`report/processor/StatisticsSummaryData.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/report/processor/StatisticsSummaryData.java)

## Distributed / aggregation

RMI master/worker: the master serializes the plan to remote engines; workers stream `SampleResult`s
back through `RemoteSampleListener`. Pluggable `SampleSender` strategies (Standard, Batch, Hold,
Statistical pre-aggregation, DataStripping) control wire volume — because sending every sample swamps
the network and the controller, which is the documented scaling bottleneck (it runs every
listener/collector for the whole fleet). Live metrics stream off the hot path via the asynchronous
`BackendListener` queue.
→ [`samplers/RemoteSampleListener.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/samplers/RemoteSampleListener.java),
[`visualizers/backend/BackendListener.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/visualizers/backend/BackendListener.java)

## Scenario / user API

A declarative XML `HashTree` test plan: TestPlan → ThreadGroup → Controllers (loop/if/transaction) →
Samplers (HTTP/JDBC/...) → Assertions / Timers / Pre-Post-Processors. Pass/fail is an `Assertion`
attaching an `AssertionResult` to the sample (Response, JSON Path, Duration, ...).
→ [`assertions/Assertion.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/assertions/Assertion.java),
[`assertions/ResponseAssertion.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/assertions/ResponseAssertion.java)

## Source basis

Cross-checked against pre-existing architecture-study notes and the pinned public source links
above.
