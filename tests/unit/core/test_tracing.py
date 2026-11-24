import json
import logging
from uuid import UUID

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.logging import JsonFormatter
from atlas_ml_platform.core.tracing import configure_tracing

TEST_DATABASE_URL = (
    "postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_test"
)


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        DATABASE_URL=TEST_DATABASE_URL,
        **overrides,
    )


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="tests.unit.core.tracing",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="inference_completed",
        args=(),
        exc_info=None,
    )


def test_configure_tracing_returns_none_when_disabled_without_exporter() -> None:
    runtime = configure_tracing(_settings(OTEL_ENABLED=False))

    assert runtime is None


def test_injected_exporter_enables_tracing_and_sets_resource_attributes() -> None:
    exporter = InMemorySpanExporter()
    runtime = configure_tracing(
        _settings(
            OTEL_ENABLED=False,
            APP_ENV="testing",
            OTEL_SERVICE_NAME="atlas-tracing-unit",
            OTEL_SERVICE_VERSION="9.9.9",
        ),
        exporter=exporter,
    )
    assert runtime is not None

    try:
        with runtime.tracer.start_as_current_span("unit.span"):
            pass
    finally:
        runtime.provider.shutdown()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "unit.span"
    assert span.resource.attributes["service.name"] == "atlas-tracing-unit"
    assert span.resource.attributes["service.version"] == "9.9.9"
    assert span.resource.attributes["deployment.environment"] == "testing"
    _ = UUID(str(span.resource.attributes["service.instance.id"]))


def test_tracer_records_nested_spans_with_parent_links() -> None:
    exporter = InMemorySpanExporter()
    runtime = configure_tracing(_settings(), exporter=exporter)
    assert runtime is not None

    try:
        with runtime.tracer.start_as_current_span("unit.parent") as parent:
            with runtime.tracer.start_as_current_span("unit.child") as child:
                child.set_attribute("unit.child", True)
            parent_context = parent.get_span_context()
    finally:
        runtime.provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert set(spans) == {"unit.parent", "unit.child"}
    child_parent = spans["unit.child"].parent
    assert child_parent is not None
    assert child_parent.span_id == parent_context.span_id
    assert spans["unit.child"].attributes["unit.child"] is True


def test_formatter_adds_trace_context_only_inside_active_span() -> None:
    exporter = InMemorySpanExporter()
    runtime = configure_tracing(_settings(), exporter=exporter)
    assert runtime is not None
    formatter = JsonFormatter(service="atlas-test", environment="testing")

    try:
        outside: dict[str, object] = json.loads(formatter.format(_record()))
        with runtime.tracer.start_as_current_span("unit.formatter") as span:
            context = span.get_span_context()
            inside: dict[str, object] = json.loads(formatter.format(_record()))
    finally:
        runtime.provider.shutdown()

    assert "trace_id" not in outside
    assert "span_id" not in outside
    assert inside["trace_id"] == format(context.trace_id, "032x")
    assert inside["span_id"] == format(context.span_id, "016x")
