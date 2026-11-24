# Tracing

## Local backend

`docker compose up -d` starts Jaeger all-in-one alongside PostgreSQL and
SeaweedFS. The application exports OTLP HTTP traces to
`http://127.0.0.1:4318`; Jaeger UI is at <http://127.0.0.1:16686>.

The backend is replaceable. Production can point
`OTEL_EXPORTER_OTLP_ENDPOINT` at an OpenTelemetry Collector or Tempo.

## Settings

| Setting | Meaning |
|---|---|
| `OTEL_ENABLED` | Enable tracing (default: false) |
| `OTEL_SERVICE_NAME` | `service.name` resource attribute |
| `OTEL_SERVICE_VERSION` | `service.version` resource attribute |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP HTTP base endpoint; `/v1/traces` is appended if omitted |
| `OTEL_TRACES_SAMPLER_ARG` | Trace ID ratio sampler in `(0, 1]` |

The provider uses `ParentBased(TraceIdRatioBased(arg))`. Production should
lower the ratio when traffic is high; the default `1.0` is for local learning.

## Spans

- FastAPI server span per request, with route, method, status, and URL
  attributes. ASGI receive/send spans are excluded to keep traces readable.
- SQLAlchemy `connect` and `SELECT`/write spans as children of the current
  application span.
- `inference.run` root span for inference, with request/model/version IDs,
  batch size, cache hit, prediction count, and outcome.
- `model.lookup` for active-version and artifact metadata queries.
- `artifact.fetch` for object download plus checksum verification.
- `model.load` for cached/deserialized runtime loading.
- `model.predict` for synchronous prediction execution in a worker thread.

Artifact fetch/load spans only appear on a cache miss. SQLAlchemy queries are
children of `model.lookup`, so a trace shows database work under the
application step that caused it.

## Correlation

W3C `traceparent` is extracted from incoming requests and propagated by the
FastAPI instrumentation. Example:

```text
traceparent: 00-11111111111111111111111111111111-2222222222222222-01
```

The server and custom spans use that trace ID. Structured logs include
`trace_id` and `span_id` when a span is active; use these fields to jump from a
log line to the trace. `request_id` is a separate HTTP correlation ID and is
returned to clients.

## Security and cost

- Span attributes intentionally omit inference feature values and request
  bodies.
- SQLAlchemy spans may include SQL text; parameters are not added as custom
  attributes.
- OTLP export is asynchronous with a batch processor. Export failures do not
  fail requests, but spans may be dropped if the backend is unavailable.
- `service.instance.id` is generated per process; it is not a hostname or
  secret.
- SQLAlchemy is pinned below 2.1 because the installed OpenTelemetry
  SQLAlchemy instrumentor supports `< 2.1.0`.
