from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export import SpanExporter

from atlas_ml_platform.api.router import api_router
from atlas_ml_platform.config import Settings, get_settings
from atlas_ml_platform.core.errors import register_exception_handlers
from atlas_ml_platform.core.lifespan import lifespan
from atlas_ml_platform.core.logging import configure_logging
from atlas_ml_platform.core.metrics import metrics_endpoint
from atlas_ml_platform.core.middleware import RequestContextMiddleware
from atlas_ml_platform.core.shutdown import RequestTracker
from atlas_ml_platform.core.tracing import configure_tracing


def create_app(
    settings: Settings | None = None,
    *,
    span_exporter: SpanExporter | None = None,
) -> FastAPI:
    if settings is None:
        settings = get_settings()

    configure_logging(settings)

    app = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade ML Model Serving Platform",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.ready = False
    app.state.shutting_down = False
    app.state.request_tracker = RequestTracker()
    app.add_middleware(RequestContextMiddleware)

    tracing_runtime = configure_tracing(settings, exporter=span_exporter)
    app.state.tracing_runtime = tracing_runtime
    app.state.tracer_provider = (
        tracing_runtime.provider if tracing_runtime is not None else None
    )
    app.state.tracer = tracing_runtime.tracer if tracing_runtime is not None else None
    if tracing_runtime is not None:
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracing_runtime.provider,
            exclude_spans=["receive", "send"],
        )

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api/v1")
    app.add_route("/metrics", metrics_endpoint, include_in_schema=False)

    return app
