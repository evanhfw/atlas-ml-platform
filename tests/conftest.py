import os

import pytest
from sqlalchemy.engine import make_url

from atlas_ml_platform.config import Settings

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_test"
)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    database = make_url(url).database
    if database != "atlas_test":
        raise RuntimeError(f"Refusing to run tests against {database!r}")
    return url


@pytest.fixture
def test_settings(test_database_url: str) -> Settings:
    return Settings(
        _env_file=None, APP_ENV="testing", DEBUG=False, DATABASE_URL=test_database_url
    )
