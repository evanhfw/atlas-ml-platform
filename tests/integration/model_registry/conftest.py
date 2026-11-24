from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.infrastructure.database.engine import create_database_engine
from atlas_ml_platform.infrastructure.database.session import create_session_factory


@pytest_asyncio.fixture
async def session_factory(
    test_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_database_engine(test_database_url)
    try:
        async with engine.connect() as connection:
            has_tables = await connection.run_sync(
                lambda sync_connection: all(
                    inspect(sync_connection).has_table(table)
                    for table in (
                        "models",
                        "model_versions",
                        "model_deployments",
                    )
                )
            )
        if not has_tables:
            pytest.fail(
                "atlas_test is not migrated; run alembic upgrade head against it"
            )
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_model_registry(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async def truncate() -> None:
        async with session_factory() as session:
            _ = await session.execute(
                text(
                    "TRUNCATE TABLE model_deployments, model_versions, models, artifacts"
                )
            )
            await session.commit()

    await truncate()
    yield
    await truncate()
