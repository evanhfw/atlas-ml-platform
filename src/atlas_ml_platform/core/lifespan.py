import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from prometheus_client import REGISTRY
from sqlalchemy import text

from atlas_ml_platform.core.metrics import DatabasePoolCollector
from atlas_ml_platform.infrastructure.database.engine import create_database_engine
from atlas_ml_platform.infrastructure.database.session import create_session_factory
from atlas_ml_platform.modules.artifacts.infrastructure import S3ArtifactStore
from atlas_ml_platform.modules.inference.application.runtime_cache import (
    ModelRuntimeCache,
)
from atlas_ml_platform.modules.inference.infrastructure import SklearnModelRuntimeLoader

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings

    engine = create_database_engine(
        database_url=settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )

    sqlalchemy_instrumented = False
    pool_collector: DatabasePoolCollector | None = None
    artifact_store: S3ArtifactStore | None = None
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)
        pool_collector = DatabasePoolCollector(engine.pool)
        REGISTRY.register(pool_collector)

        tracing_runtime = app.state.tracing_runtime
        if tracing_runtime is not None:
            SQLAlchemyInstrumentor().instrument(
                engine=engine.sync_engine,
                tracer_provider=tracing_runtime.provider,
            )
            sqlalchemy_instrumented = True
            logger.info("SQLAlchemy tracing enabled")

        logger.info("Database connection established")

        artifact_store = await S3ArtifactStore.create(
            endpoint=settings.S3_ENDPOINT,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            secure=settings.S3_SECURE,
            connect_timeout_seconds=settings.S3_CONNECT_TIMEOUT_SECONDS,
            read_timeout_seconds=settings.S3_READ_TIMEOUT_SECONDS,
            max_attempts=settings.S3_MAX_ATTEMPTS,
        )
        app.state.artifact_store = artifact_store
        logger.info("Artifact store ready: %s", settings.S3_BUCKET)

        app.state.model_runtime_cache = ModelRuntimeCache(
            SklearnModelRuntimeLoader(),
            max_entries=settings.MODEL_CACHE_MAX_ENTRIES,
            load_timeout_seconds=settings.MODEL_LOAD_TIMEOUT_SECONDS,
        )
        logger.info(
            "Model runtime cache ready: max_entries=%d",
            settings.MODEL_CACHE_MAX_ENTRIES,
        )

        app.state.ready = True
        logger.info("Readiness enabled")
        yield

    finally:
        app.state.ready = False
        app.state.shutting_down = True

        tracker = getattr(app.state, "request_tracker", None)
        if tracker is not None:
            if tracker.in_flight > 0:
                logger.info(
                    "Draining in-flight requests: count=%d grace_seconds=%s",
                    tracker.in_flight,
                    settings.SHUTDOWN_GRACE_SECONDS,
                )
            drained = await tracker.wait_for_idle(settings.SHUTDOWN_GRACE_SECONDS)
            if not drained:
                logger.warning(
                    "Shutdown grace period elapsed with in-flight requests: count=%d",
                    tracker.in_flight,
                )

        if pool_collector is not None:
            with suppress(KeyError):
                REGISTRY.unregister(pool_collector)

        tracing_runtime = app.state.tracing_runtime
        if tracing_runtime is not None:
            if sqlalchemy_instrumented:
                SQLAlchemyInstrumentor().uninstrument()
            FastAPIInstrumentor.uninstrument_app(app)
            tracing_runtime.provider.shutdown()

        if artifact_store is not None:
            try:
                await artifact_store.close()
            except Exception:
                logger.exception("Failed to close artifact store")

        await engine.dispose()
        logger.info("Shutting down %s", settings.APP_NAME)
