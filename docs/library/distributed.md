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

Use {class}`~rampa.distributed.segment.ExecutionSegment` to partition
work deterministically across workers without central assignment:

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
Archives are input bundles, not result stores. In a distributed run, the
coordinator aggregates worker samples and output backends decide where
results are retained: local JSON/CSV artifacts, remote metric stores, CI
summaries, or custom ingestion.

For programmatic use,
{func}`~rampa.distributed.archive.create_archive` builds the bundle and
{func}`~rampa.distributed.archive.extract_archive` returns an
{class}`~rampa.distributed.archive.ArchiveManifest` when unpacking it:

```python
from rampa.distributed.archive import create_archive, extract_archive

create_archive("load_test.py", "test.rampa", requirements=["aiohttp>=3.9"])
manifest = extract_archive("test.rampa", "/tmp/work")
```

## Wire protocol

Coordinator and workers communicate via WebSocket using MessagePack
(JSON fallback). Message types: `register`, `assign`, `samples`,
`stop`, `heartbeat_req/resp`, `threshold_breach`.
