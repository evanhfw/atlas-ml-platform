# Performance baseline and capacity

## Scope

This is a repeatable local baseline, not a production capacity guarantee.
Locust, the API (one uvicorn worker), PostgreSQL, SeaweedFS, Jaeger,
Prometheus, and Grafana ran on the same workstation.

Host:

- 8 logical CPUs (12th Gen Intel Core i3-1215U)
- 15 GiB RAM
- Linux 6.18
- App: `uvicorn`, one worker, `OTEL_ENABLED=true`, `LOG_LEVEL=INFO`
- Database pool: `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10` (max 15 per process)
- PostgreSQL `max_connections=100`
- Model: deterministic iris `StandardScaler + LogisticRegression`, joblib
  artifact, loaded into the in-process runtime cache

## Workload

Locust task mix:

| Weight | Request |
|---|---|
| 6 | `POST /api/v1/models/{model_id}/predictions` |
| 3 | `GET /api/v1/models/{model_id}` |
| 1 | `GET /api/v1/artifacts/{artifact_id}` |
| 1 | `GET /api/v1/health` |

Two runs:

- **Baseline:** 20 users, spawn rate 5/s, 60 seconds.
- **Stress:** 40 users, spawn rate 10/s, 30 seconds.

The model was prepared and warmed before each run by
`loadtest/prepare.py`. Setup failures are not part of the Locust results.

## Results

### Baseline, 20 users

| Metric | Result |
|---|---|
| Total requests | 4,512 |
| Failure rate | 0% |
| Throughput | 76.1 req/s |
| p50 / p95 / p99 | 120 / 310 / 410 ms |
| Inference requests | 2,459 |
| Inference p50 / p95 / p99 | 160 / 350 / 450 ms |
| Model read p95 | 190 ms |
| Artifact metadata p95 | 180 ms |
| Health p95 | 56 ms |
| App CPU average / max | 76.2% / 98.9% |
| App RSS range | 211.3–212.9 MiB |
| DB pool checked-out max | 12 / 15 |
| Cold inference | 1,942 ms |
| Warm single-request inference | 25 ms |
| Model load | 1.898 s |
| Artifact read (cold) | 10.9 ms |

### Stress, 40 users

| Metric | Result |
|---|---|
| Total requests | 2,446 |
| Failure rate | 0% |
| Throughput | 83.9 req/s |
| p50 / p95 / p99 | 330 / 690 / 950 ms |
| Inference p50 / p95 / p99 | 430 / 790 / 1,000 ms |
| App CPU average / max | 71.6% / 97.9% |
| App RSS range | 212.6–214.7 MiB |
| DB pool checked-out max | 14 / 15 |

Throughput rose only from 76 to 84 req/s while p95 more than doubled from
310 to 690 ms. That is saturation behavior, not linear scaling.

## Measurements

- Client latency and throughput: Locust CSV.
- App CPU/RSS/threads: `loadtest/observe.py` via `psutil`.
- Pool high-water mark: Prometheus
  `max_over_time(atlas_db_pool_connections{state="checked_out"}[...])`.
- Model load and artifact read: Prometheus histograms.
- Logs/traces: correlated by request and trace ID from M10/M11.

The Prometheus histogram p95 can differ from Locust's client-observed p95
because of bucket interpolation and time-window aggregation. Use Locust for
client latency; use Prometheus for stage and pool behavior.

## Capacity model

Little's Law:

```text
concurrency ≈ throughput × latency
```

At baseline, approximately `76.1 × 0.129 ≈ 9.8` concurrent requests; the
configured 20 virtual users include think time. At stress, the observed
latency rose while throughput plateaued, indicating queueing/CPU contention.

Pool budget per process:

```text
max connections = DB_POOL_SIZE + DB_MAX_OVERFLOW = 15
```

For `W` app workers and `R` replicas:

```text
W × R × 15 <= 0.7 × max_connections
```

With PostgreSQL `max_connections=100`, four workers at 15 connections each
would use 60 connections, leaving headroom for migrations and operations.
Do not raise pool size until CPU/queueing and PostgreSQL connection usage are
measured under the intended worker/replica count.

## Supported bottlenecks

1. **CPU saturation.** App CPU reached ~98% while throughput plateaued and
   p95 increased. sklearn prediction and model loading are CPU-heavy.
2. **Pool pressure.** Checked-out connections reached 14/15 during stress.
   Further concurrency can wait on the pool and increase tail latency.
3. **Per-inference database work.** Each inference resolves the active
   version and artifact metadata through several SQL queries. Traces show
   these under `model.lookup`; this contributes to pool pressure.
4. **Cold model load.** First inference was ~1.94 s (load ~1.90 s), while a
   warm request was ~25 ms. The in-process cache works, but cold starts are
   expensive.
5. **Runtime threading.** Prediction threads and application work shared the
   same process CPU; RSS was stable, so there is no evidence of a memory leak
   in these short runs.

## Prioritized next experiments

No optimization is applied here without evidence.

1. Measure OTEL sampling/export overhead by repeating the baseline with
   tracing disabled.
2. Cache active-version/artifact metadata with bounded TTL and explicit
   invalidation on activation; measure DB pool and p95 impact.
3. Test 4 uvicorn workers against the same PostgreSQL budget before changing
   pool sizing.
4. Evaluate process-based inference isolation if CPU saturation persists
   after metadata caching.
5. Preload the active model on activation if cold-start latency matters for
   the serving SLO.
6. Define an SLO and run a longer soak test; current runs are 30–60 seconds.

## Environment note

During setup, the local SeaweedFS instance exhausted its default volume slots
because test and development collections each allocate volumes. The local
entrypoint now sets `-volume.max=100`; this is a development capacity fix, not
a production storage design. Empty test volumes were removed before the
baseline.

## Reproduce

Start the app (single worker) and then:

```bash
BASE_URL=http://127.0.0.1:8000 USERS=20 DURATION=60s \
  ./loadtest/run_baseline.sh
```

Results are written under `loadtest/results/` and are gitignored. The
benchmark model is created in the development database with a unique name.
