import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from atlas_ml_platform.core.application import create_app
from atlas_ml_platform.infrastructure.database.engine import create_database_engine


@pytest.fixture(autouse=True)
def clean_model_registry(test_database_url: str) -> Iterator[None]:
    async def truncate() -> None:
        engine = create_database_engine(test_database_url)
        try:
            async with engine.begin() as connection:
                _ = await connection.execute(
                    text(
                        "TRUNCATE TABLE model_deployments, model_versions, models, artifacts"
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(truncate())
    yield
    asyncio.run(truncate())


@pytest.fixture
def client(test_settings) -> Iterator[TestClient]:
    app = create_app(settings=test_settings)
    with TestClient(app) as test_client:
        yield test_client
