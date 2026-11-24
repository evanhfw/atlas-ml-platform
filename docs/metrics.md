# Metrics and dashboards

## Endpoint

The application exposes Prometheus text exposition at `GET /metrics` on the
API process, not under `/api/v1`. The endpoint is excluded from HTTP request
metrics and access logging to avoid self-scrape noise.

## Metric catalogue

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `atlas_http_requests_total` | counter | `method`, `route`, `status_code` | HTTP requests |
| `atlas_http_request_duration_seconds` | histogram | `method`, `route` | HTTP latency |
| `atlas_inference_requests_total` | counter | `outcome`, `cache_hit` | Inference requests |
| `atlas_inference_duration_seconds` | histogram | `outcome`, `cache_hit` | End-to-end inference latency |
| `atlas_model_load_total` | counter | `outcome` | Runtime cache misses and load results |
| `atlas_model_load_duration_seconds` | histogram | `outcome` | Deserialization duration |
| `atlas_artifact_read_total` | counter | `outcome` | Artifact fetch/checksum results |
| `atlas_artifact_read_duration_seconds` | histogram | `outcome` | Artifact read duration |
| `atlas_db_pool_connections` | gauge | `state` | SQLAlchemy pool size/checked in/checked out |

`route` uses the FastAPI operation name, for example `predict`,
`create_model`, or `health_check`. This keeps labels bounded and avoids
putting model UUIDs or raw paths into Prometheus.

`outcome` values are bounded: `success`, `error`, `timeout`,
`invalid_input`, or `integrity_error` depending on the metric. `cache_hit` is
`true` or `false`.

## Cardinality rules

- Never label metrics with model IDs, version IDs, artifact IDs, request IDs,
  user input, or raw URL paths.
- HTTP status codes are finite and safe as labels.
- Add new label values only when the set is intentionally finite.
- Keep artifact/model identity in logs and traces, not Prometheus labels.

The Prometheus client registry is process-local. The documented uvicorn
command runs one worker. A multi-worker deployment needs multiprocess
collection or per-worker scraping; otherwise each process exposes only its own
counters.

## Local stack

`docker compose up -d` starts:

- Prometheus at <http://127.0.0.1:9090>, scraping
  `127.0.0.1:8000/metrics` every 15 seconds.
- Grafana at <http://127.0.0.1:3002>, with the `Atlas ML Platform` dashboard
  provisioned under the Atlas folder.
- Jaeger remains the local trace UI at <http://127.0.0.1:16686>.

Prometheus and Grafana use host networking because the API is run directly by
uvicorn on the host at `127.0.0.1:8000`. This is a Linux development setup; a
containerized API would instead use a Compose network target.

The Grafana admin password defaults to `admin` for local use. Set
`GRAFANA_ADMIN_PASSWORD` in `.env` for any shared environment.

## Dashboard

The provisioned dashboard includes:

- HTTP request rate by operation and status.
- HTTP p95 latency by operation.
- HTTP 4xx/5xx error rate.
- Inference rate by outcome and cache hit.
- Inference p95 latency by cache hit.
- Model load outcomes.
- SQLAlchemy pool connections.

Dashboard JSON: `docker/grafana/dashboards/atlas-ml-platform.json`.
Provisioning: `docker/grafana/provisioning/`.

## Security

`/metrics` has no authentication in this slice. Expose it only on a trusted
network, or put it behind network policy / a reverse proxy in production.
Metric labels deliberately exclude payloads and high-cardinality identifiers.
