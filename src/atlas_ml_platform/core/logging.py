import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID

from opentelemetry import trace

from atlas_ml_platform.config import Settings

request_id_var: ContextVar[UUID | None] = ContextVar("request_id", default=None)
method_var: ContextVar[str | None] = ContextVar("method", default=None)
path_var: ContextVar[str | None] = ContextVar("path", default=None)

_EXTRA_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_code",
    "error_type",
    "model_id",
    "version_id",
    "rows",
    "latency_ms",
    "outcome",
)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record with safe request context."""

    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self._service: str = service
        self._environment: str = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service,
            "environment": self._environment,
        }

        request_id = getattr(record, "request_id", None) or request_id_var.get()
        if request_id is not None:
            payload["request_id"] = str(request_id)

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")

        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings) -> None:
    """Install the application JSON handler exactly once per process."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(service=settings.APP_NAME, environment=settings.APP_ENV)
    )
    handler._atlas_json_handler = True  # type: ignore[attr-defined]

    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_atlas_json_handler", False):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL)
