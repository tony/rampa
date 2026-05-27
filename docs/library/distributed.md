(distributed)=

# Distributed execution

rampa supports splitting load tests across multiple machines for
higher throughput. The coordinator manages workers and aggregates
metrics centrally.

## Architecture

```
Coordinator (your machine)
  ├── MetricEngine (aggregated)
  ├── Threshold evaluation (centralized)
  └── WebSocket server
       ├── Worker 0 (SSH / Lambda / ECS)
       ├── Worker 1
       └── Worker N
```

Workers connect to the coordinator, receive work segments, run the
test locally, and stream samples back.

## Execution segments

Work is deterministically partitioned across workers without central
assignment:

```python
from rampa.distributed.segment import ExecutionSegment

seg = ExecutionSegment(index=0, total=3)
seg.vu_range(30)       # range(0, 10)
seg.scale_rate(1000.0)  # 333.3
```

Each worker independently computes its share from its index and the
total worker count.

## Test archives

Self-contained `.rampa` zip bundles contain everything a remote
worker needs:

```console
$ rampa archive create load_test.py -o test.rampa
```

Contents: script, data files, `requirements.txt`, `manifest.json`.

```python
from rampa.distributed.archive import create_archive, extract_archive

create_archive("load_test.py", "test.rampa", requirements=["aiohttp>=3.9"])
manifest = extract_archive("test.rampa", "/tmp/work")
```

## Wire protocol

Coordinator and workers communicate via WebSocket using MessagePack
(JSON fallback). Message types: `register`, `assign`, `samples`,
`stop`, `heartbeat_req/resp`, `threshold_breach`.
