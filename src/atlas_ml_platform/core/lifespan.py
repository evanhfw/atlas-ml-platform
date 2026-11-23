import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from atlas_ml_platform.infrastructure.database.engine import create_database_engine
from atlas_ml_platform.infrastructure.database.session import create_session_factory

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

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)

        logger.info("Database connection established")

        yield

    finally:
        await engine.dispose()
        logger.info("Shutting down %s", settings.APP_NAME)
