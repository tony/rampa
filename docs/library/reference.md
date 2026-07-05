(api-reference)=

# API Reference

## Configuration

```{eval-rst}
.. automodule:: rampa.config
   :members: Config, ScenarioConfig, Stage, Options, parse_duration
```

## Engine

```{eval-rst}
.. automodule:: rampa.engine
   :members: Engine, EngineOptions, RunController
```

## Event Bus

```{eval-rst}
.. automodule:: rampa.bus
   :members: EventBus
```

## Events

```{eval-rst}
.. automodule:: rampa.events
   :members: RunStatus, RunResult, EngineEvent, PhaseEvent, SnapshotEvent, ThresholdEvent, LiveThresholdEvent
```

## Worker

```{eval-rst}
.. automodule:: rampa.worker
   :members: Worker, ExecutionInfo
```

## HTTP Client

```{eval-rst}
.. automodule:: rampa.http
   :members: HttpClient, Response
```

## Metrics

```{eval-rst}
.. automodule:: rampa.metrics
   :members: MetricSnapshot, MetricRegistry, MetricEngine, SinkProtocol
```

## Outputs

```{eval-rst}
.. autoclass:: rampa.output.Output
   :members:

.. autoclass:: rampa.output.OutputManager
   :members:

.. autofunction:: rampa.outputs.get_output
```

## Thresholds

```{eval-rst}
.. automodule:: rampa.thresholds
   :members: ThresholdResult, parse_threshold, evaluate_thresholds
```

## Distributed Execution

```{eval-rst}
.. automodule:: rampa.distributed.segment
   :members: ExecutionSegment

.. automodule:: rampa.distributed.archive
   :members: ArchiveManifest, create_archive, extract_archive
```

## CI Comparison

```{eval-rst}
.. automodule:: rampa.ci.compare
   :members: MetricDelta, compare_results, format_text, format_markdown, format_json
```

## Loader

```{eval-rst}
.. automodule:: rampa.loader
   :members: TestPlan, scenario, load_test
```
