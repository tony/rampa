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

## Events

```{eval-rst}
.. automodule:: rampa.events
   :members: RunStatus, RunResult, EngineEvent, PhaseEvent, SnapshotEvent, ThresholdEvent
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

## Thresholds

```{eval-rst}
.. automodule:: rampa.thresholds
   :members: ThresholdResult, parse_threshold, evaluate_thresholds
```

## Loader

```{eval-rst}
.. automodule:: rampa.loader
   :members: TestPlan, scenario, load_test
```
