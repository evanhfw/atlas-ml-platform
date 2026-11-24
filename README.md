# Atlas ML Platform

A production-oriented ML model management and serving platform, built as a
modular monolith with Clean Architecture boundaries.

Current scope: FastAPI application foundation, validated settings, async
PostgreSQL lifecycle, S3-compatible object storage, artifact upload/download
API, scikit-learn inference runtime, structured logging, request correlation,
OpenTelemetry tracing, Prometheus metrics, Grafana dashboards, readiness and
graceful shutdown, reproducible load-test baseline, health endpoints, and
Alembic migrations.

Product requirements and roadmap: [`prd.md`](prd.md).

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose

## Setup

1. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

   Set `POSTGRES_PASSWORD` and `S3_SECRET_KEY`, and make the password in
   `DATABASE_URL` match `POSTGRES_PASSWORD`. The same `S3_ACCESS_KEY` and
   `S3_SECRET_KEY` configure both SeaweedFS and the application. The defaults
   target `atlas_dev` on `localhost:5432`. `.env` is gitignored; never commit
   real credentials.

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Start PostgreSQL, SeaweedFS, Jaeger, Prometheus, and Grafana:

   ```bash
   docker compose up -d
   docker compose ps
   ```

   Wait until all containers are `healthy`. PostgreSQL is bound to
   `127.0.0.1:5432`; SeaweedFS exposes the S3 API on `127.0.0.1:8333`;
   Jaeger exposes OTLP HTTP on `127.0.0.1:4318` and its UI on
   `127.0.0.1:16686`; Prometheus is on `127.0.0.1:9090`; Grafana is on
   `127.0.0.1:3002`. Prometheus and Grafana use host networking so they can
   scrape the local uvicorn process at `127.0.0.1:8000` (Linux dev setup).

4. Apply migrations to the development database:

   ```bash
   uv run alembic upgrade head
   ```

5. On a fresh volume, Compose creates both `atlas_dev` and `atlas_test`.
   `atlas_dev` comes from `POSTGRES_DB`; `atlas_test` is created by
   `docker/postgres/init/01-create-test-db.sh`.

   Initialization scripts run only when the PostgreSQL data directory is
   empty. For a volume created before this script existed, create the test
   database manually:

   ```bash
   docker compose exec postgres \
     psql -U atlas -d postgres -c 'CREATE DATABASE atlas_test OWNER atlas;'
   ```

   `atlas_test` is separate from `atlas_dev` on purpose.

## Object storage

Local S3-compatible storage uses SeaweedFS at `http://127.0.0.1:8333`.
Credentials and bucket configuration come from the `S3_*` variables in
`.env`. The application uses the S3 API, so production can point the same
settings at managed S3 storage.

MinIO's official Docker images were removed from Docker Hub and the community
edition is no longer the safe default. SeaweedFS is used locally instead; the
`ArtifactStore` port and S3 adapter keep the backend replaceable.

## Run

```bash
uv run uvicorn atlas_ml_platform.main:app \
  --reload --no-access-log --timeout-graceful-shutdown 30
```

The request middleware emits one structured access log per request;
`--no-access-log` avoids a duplicate unstructured Uvicorn access line.
Log fields and the error contract are documented in
[`docs/logging.md`](docs/logging.md).

- API docs: <http://127.0.0.1:8000/docs>
- Liveness: `GET /api/v1/health`
- Readiness: `GET /api/v1/health/ready`

`/api/v1/health` does not touch dependencies. Readiness checks PostgreSQL and
S3 concurrently and returns `503` while starting, while draining, or when a
dependency is unavailable. The shutdown sequence and timeout policy are in
[`docs/reliability.md`](docs/reliability.md).

## Artifact API

Upload a file as multipart field `file`:

```bash
curl -F 'file=@model.joblib;type=application/octet-stream' \
  http://127.0.0.1:8000/api/v1/artifacts
```

The response contains `id`, `uri`, `checksum`, `size_bytes`, `content_type`,
and `created_at`. Metadata is stored in PostgreSQL; bytes are stored in
SeaweedFS. Use the returned `uri` as a model version's `artifact_uri`.
Version creation rejects an unregistered artifact URI with `404`, and version
responses include the resolved artifact metadata under `artifact`.

- `GET /api/v1/artifacts/{id}` returns metadata.
- `GET /api/v1/artifacts/{id}/content` returns the bytes and verifies SHA-256.
- Uploads over `ARTIFACT_MAX_SIZE_BYTES` return `413`; disallowed content
  types return `415`.

The current slice reads the whole upload into memory. Streaming uploads and
presigned URLs are intentionally deferred.

## Inference

The first runtime is a deterministic scikit-learn `LogisticRegression` on the
iris dataset.

1. Generate the example artifact:

   ```bash
   uv run python scripts/create_example_model.py
   ```

2. Choose the artifact trust policy in `.env`.

   For local development, `.env.example` uses:

   ```dotenv
   ARTIFACT_TRUST_POLICY=auto
   ```

   This makes upload → version → activate → predict work immediately without
   editing per-artifact checksums. It trusts every upload, so never expose a
   development server to untrusted users. The application refuses to start
   with `ARTIFACT_TRUST_POLICY=auto` when `APP_ENV=production`.

   Production must use `ARTIFACT_TRUST_POLICY=allowlist` and list trusted
   SHA-256 checksums:

   ```dotenv
   TRUSTED_ARTIFACT_CHECKSUMS=<printed-checksum>
   ```

   `joblib`/pickle deserialization can execute arbitrary code. Never add a
   checksum for an upload you did not produce or inspect.

3. Upload `example_model.joblib` with content type `application/x-joblib`,
   then create a model, create a version using the returned artifact `uri`,
   mark the version ready, and activate it. These steps are available in
   Swagger UI at `/docs`.

4. Run inference against the active version:

   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/models/<model-id>/predictions \
     -H 'content-type: application/json' \
     -d '{"features": [[5.1, 3.5, 1.4, 0.2]]}'
   ```

   Response includes `request_id`, model/version identifiers, `predictions`,
   and `latency_ms`.

Runtime behavior:

- Loaded models are cached by artifact URI + SHA-256 in a process-local LRU
  cache (`MODEL_CACHE_MAX_ENTRIES`).
- Artifact download and model loading have a deadline
  (`MODEL_LOAD_TIMEOUT_SECONDS`); prediction has its own deadline
  (`INFERENCE_TIMEOUT_SECONDS`).
- Deserialization and prediction run in worker threads so CPU-bound work does
  not block the event loop.
- Invalid feature matrices or a model feature-count mismatch return `422`.
  Untrusted, corrupt, or unloadable artifacts return `500`; timeouts return
  `504`.

## Tracing

OpenTelemetry tracing is enabled by `.env.example` locally:

```dotenv
OTEL_ENABLED=true
OTEL_SERVICE_NAME=atlas-ml-platform
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
OTEL_TRACES_SAMPLER_ARG=1.0
```

Jaeger is part of `docker compose`; open <http://127.0.0.1:16686> and select
the `atlas-ml-platform` service.

Each API request produces a server span. Inference adds child spans for model
lookup, artifact fetch, model load, and prediction; SQLAlchemy queries appear
as children of the model lookup span. W3C `traceparent` is propagated.
Structured logs include `trace_id` and `span_id` when a span is active, so a
log line can be correlated with the trace.

Example propagation header:

```text
traceparent: 00-11111111111111111111111111111111-2222222222222222-01
```

Production can replace the local Jaeger endpoint with an OTel Collector or
Tempo. See [`docs/tracing.md`](docs/tracing.md).

## Metrics and dashboards

The application exposes Prometheus metrics at:

```text
http://127.0.0.1:8000/metrics
```

Prometheus scrapes it every 15 seconds; Grafana is provisioned with the
`Atlas ML Platform` dashboard. Local Grafana login is `admin` / `admin` unless
`GRAFANA_ADMIN_PASSWORD` is set.

- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3002>

Metrics include HTTP request rate/latency/status, inference outcomes and
cache hits, model loads, artifact reads, and SQLAlchemy pool state. Labels use
bounded operation names and outcomes; model/version IDs are not metric labels.

See [`docs/metrics.md`](docs/metrics.md) for the metric catalogue, cardinality
rules, and dashboard details.

## Performance baseline

The repeatable Locust workload and benchmark setup live under `loadtest/`.
Start the app with one worker, then run:

```bash
BASE_URL=http://127.0.0.1:8000 USERS=20 DURATION=60s \
  ./loadtest/run_baseline.sh
```

The script creates and activates a deterministic iris model, warms it, runs
Locust, and samples app CPU/RSS. Results are written under
`loadtest/results/` and are gitignored.

The measured baseline, stress results, capacity model, evidence-backed
bottlenecks, and prioritized experiments are in
[`docs/performance.md`](docs/performance.md). Local results are relative to
this workstation and are not production capacity guarantees.

## Tests

```bash
uv run pytest
```

Tests use `atlas_test`, never `atlas_dev`. `tests/conftest.py` fails closed if
the target database name is not `atlas_test`.

Override the test database with:

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://atlas:CHANGE_ME@localhost:5432/atlas_test"
uv run pytest
```

Use the same password as `POSTGRES_PASSWORD`.

Alembic reads `DATABASE_URL`, not `TEST_DATABASE_URL`. To migrate the test
database:

```bash
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

## Migrations

```bash
uv run alembic current        # applied revision
uv run alembic upgrade head   # apply pending migrations
uv run alembic check          # fail if metadata and database drift
```

Create a migration after changing ORM models:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Review the generated file before applying it. `Base.metadata` is assembled
from each module's `infrastructure/records.py`; every new records module must
be imported by `migrations/env.py`, otherwise autogenerate cannot see it.

Test upgrade and downgrade against `atlas_test`, not the development database:

```bash
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic downgrade base
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

## Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Destructive operations

```bash
docker compose down -v
```

This deletes the `atlas_postgres_data`, `atlas_seaweedfs_data`,
`atlas_prometheus_data`, and `atlas_grafana_data` volumes, including both
databases, stored artifacts, and monitoring state. It cannot be undone. On
the next `docker compose up -d`, the init script recreates both databases;
migrations must be applied again.

## Layout

```text
src/atlas_ml_platform/
├── api/                 # HTTP routes and dependencies
├── core/                # app factory, lifespan, logging, middleware, tracing
├── infrastructure/
│   └── database/        # engine, sessions, ORM base
├── modules/
│   ├── artifacts/
│   │   ├── domain/      # artifact metadata invariants
│   │   ├── application/ # store/repository ports and use cases
│   │   ├── infrastructure/  # S3 store, ORM record, repository
│   │   └── presentation/    # artifact HTTP routes
│   ├── inference/
│   │   ├── domain/      # input validation and inference errors
│   │   ├── application/ # runtime ports, cache, run-inference use case
│   │   ├── infrastructure/  # scikit-learn/joblib runtime adapter
│   │   └── presentation/    # prediction HTTP route
│   └── model_registry/
│       ├── domain/      # entity and value objects
│       ├── application/ # ports and use cases
│       └── infrastructure/  # ORM models, repositories, unit of work
└── config.py            # typed settings

docker/
├── postgres/init/       # local-only database bootstrap scripts
├── seaweedfs/           # local S3 credentials bootstrap
├── prometheus/          # local scrape configuration
└── grafana/             # datasource, dashboard provisioning, JSON dashboard

migrations/              # Alembic environment and revisions
docs/                    # logging, tracing, metrics, reliability, performance guides
scripts/                 # example model artifact generation
loadtest/                # Locust workload, setup, resource sampler, results
tests/
├── unit/                # domain/application tests
├── integration/         # real PostgreSQL tests
└── e2e/                 # API tests through the ASGI app
```
