import uuid
from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Tracer

from atlas_ml_platform.config import Settings

_TRACER_NAME = "atlas_ml_platform"


@dataclass(frozen=True, slots=True)
class TracingRuntime:
    provider: TracerProvider
    tracer: Tracer


def configure_tracing(
    settings: Settings,
    *,
    exporter: SpanExporter | None = None,
) -> TracingRuntime | None:
    """Create a tracer provider; tests can inject an in-memory exporter."""
    if not settings.OTEL_ENABLED and exporter is None:
        return None

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": settings.OTEL_SERVICE_VERSION,
            "deployment.environment": settings.APP_ENV,
            "service.instance.id": str(uuid.uuid4()),
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(root=TraceIdRatioBased(settings.OTEL_TRACES_SAMPLER_ARG)),
    )

    span_exporter = exporter or OTLPSpanExporter(
        endpoint=_traces_endpoint(settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    )
    # An injected exporter is a test concern; keep spans synchronous there.
    processor = (
        SimpleSpanProcessor(span_exporter)
        if exporter is not None
        else BatchSpanProcessor(span_exporter)
    )
    provider.add_span_processor(processor)

    return TracingRuntime(
        provider=provider,
        tracer=provider.get_tracer(_TRACER_NAME, settings.OTEL_SERVICE_VERSION),
    )


def _traces_endpoint(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/v1/traces"):
        return base
    return f"{base}/v1/traces"
