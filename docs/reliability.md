# Reliability and shutdown

## Health endpoints

| Endpoint | Purpose | Behavior |
|---|---|---|
| `GET /api/v1/health` | Liveness | `200` while the process is alive; does not touch dependencies |
| `GET /api/v1/health/ready` | Readiness | `200` only when startup completed, shutdown has not begun, PostgreSQL and S3 are reachable |

Readiness checks database `SELECT 1` and S3 `HeadBucket` concurrently, each
bounded by `READINESS_TIMEOUT_SECONDS`. During startup and shutdown it returns
`503`; dependency failures return `503` with a safe `checks` map.

## Startup

The application is not ready until the lifespan has:

1. Connected to PostgreSQL and registered metrics.
2. Instrumented SQLAlchemy when tracing is enabled.
3. Connected to S3 and verified the bucket.
4. Built the model runtime cache.

Only then is `app.state.ready` set to true. A failed startup is a failed
process, not a partially ready server.

## Shutdown sequence

On lifespan shutdown:

1. `ready` becomes false and `shutting_down` becomes true.
2. Non-probe HTTP requests receive `503 service_unavailable`; liveness,
   readiness, and `/metrics` remain reachable.
3. In-flight application requests are drained for up to
   `SHUTDOWN_GRACE_SECONDS`.
4. Metrics collector is unregistered; tracing is uninstrumented and the
   tracer provider is shut down, flushing spans.
5. The S3 client is closed.
6. The SQLAlchemy engine is disposed.

If the drain deadline expires, the application logs the remaining in-flight
count and proceeds with bounded shutdown. Threads spawned for model loading or
prediction cannot be force-killed; request-level timeouts bound how long they
are awaited.

## Server and container settings

Documented uvicorn command:

```bash
uv run uvicorn atlas_ml_platform.main:app \
  --reload --no-access-log --timeout-graceful-shutdown 30
```

`SHUTDOWN_GRACE_SECONDS` defaults to 20 seconds. Keep the server/container
termination period above the application drain period. For a future app
container, use an equivalent stop grace period:

```yaml
stop_grace_period: 30s
```

A load balancer or orchestrator should stop routing after readiness returns
`503`; liveness should remain `200` until the process exits.

## External dependency policy

- PostgreSQL: pool acquisition is bounded by `DB_POOL_TIMEOUT`; readiness uses
  `READINESS_TIMEOUT_SECONDS`; the engine is disposed at shutdown.
- S3: connect timeout `S3_CONNECT_TIMEOUT_SECONDS`, read timeout
  `S3_READ_TIMEOUT_SECONDS`, standard retries with `S3_MAX_ATTEMPTS`; the
  readiness check uses the same client.
- Inference: artifact retrieval/model load uses `MODEL_LOAD_TIMEOUT_SECONDS`;
  prediction uses `INFERENCE_TIMEOUT_SECONDS`.
- Tracing: OTLP export is batched; provider shutdown flushes pending spans.
  Export failures do not fail requests.

## Background work

The application does not start its own long-lived background jobs. Request
tasks are tracked; OTel batch export is flushed at shutdown. Model loading and
prediction run in worker threads and are bounded by request timeouts, but a
thread cannot be forcibly terminated.

## Operational checks

```bash
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/health/ready
```

During a controlled shutdown, readiness should flip to `503` while liveness
stays `200`; ordinary API calls should return the `service_unavailable` error
contract.
