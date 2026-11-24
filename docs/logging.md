# Logging and error contract

## Log format

Application logs are one JSON object per line on stdout. Uvicorn access logs
are disabled in the documented run command so the request middleware remains
the single access-log source.

Core fields:

| Field | Meaning |
|---|---|
| `timestamp` | UTC ISO-8601 timestamp |
| `level` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logger` | Python logger name |
| `message` | Short event name |
| `service` | `APP_NAME` |
| `environment` | `APP_ENV` |
| `request_id` | Correlation UUID, when inside a request |
| `trace_id`, `span_id` | Active OpenTelemetry span identifiers, when tracing is active |
| `method` | HTTP method |
| `path` | Request path, without query string |
| `status_code` | HTTP status |
| `duration_ms` | Request or operation duration |
| `error_code` | Stable machine-readable error code |
| `error_type` | Exception class name |
| `model_id`, `version_id` | Inference model/version identifiers |
| `rows` | Inference batch size |
| `latency_ms` | Inference latency |
| `outcome` | Operation outcome, for example `success` |
| `exception` | Formatted traceback for unhandled errors only |

The request middleware emits exactly one access/error record per HTTP request.
Domain exception handlers translate exceptions into responses and annotate the
request but do not emit a second error log. Unhandled exceptions are logged
once by the middleware with a traceback.

When OpenTelemetry tracing is active, log records also carry `trace_id` and
`span_id`; use those to open the corresponding trace in Jaeger or the
configured OTLP backend.

## Request correlation

- A valid UUID in `X-Request-ID` is reused; otherwise a new UUID is generated.
- The effective ID is returned in the `X-Request-ID` response header.
- Error bodies include it as `request_id`.
- Successful inference responses use the same ID as the HTTP request.
- Application log records inside the request inherit the ID through a
  context variable.

## Error response contract

Handled errors return JSON:

```json
{
  "detail": "Model not found: ...",
  "error_code": "model_not_found",
  "request_id": "11111111-1111-4111-8111-111111111111"
}
```

`detail` is a string for handled domain errors and a list for request
validation errors. `error_code` is stable for clients; `request_id` is present
when the request middleware ran. Unhandled exceptions return
`{"detail": "Internal server error", "error_code": "internal_error", ...}`
without exposing the exception or traceback to the client.

## Data that must not be logged

- Request/response bodies.
- Inference feature values.
- Authorization headers, cookies, API keys, S3 secrets, database URLs.
- Raw artifact bytes.
- Full exception payloads in client responses.

The middleware logs method, path (no query string), status, duration, and IDs.
Inference logs model/version IDs, batch size, and latency, never feature values.
