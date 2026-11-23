import pytest
from pydantic import ValidationError

from atlas_ml_platform.config import Settings

TEST_DATABASE_URL = (
    "postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_test"
)


def test_default_settings(test_database_url):
    settings = Settings(_env_file=None, DATABASE_URL=TEST_DATABASE_URL)  # pyright: ignore[reportCallIssue]

    assert settings.APP_NAME == "Atlas ML Platform"
    assert settings.APP_ENV == "development"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == test_database_url

    assert settings.DB_POOL_SIZE == 5
    assert settings.DB_MAX_OVERFLOW == 10
    assert settings.DB_POOL_TIMEOUT == 30
    assert settings.DB_POOL_RECYCLE == 1800


def test_invalid_pool_size_fails(test_database_url):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL=test_database_url,
            DB_POOL_SIZE=0,
        )


def test_custom_settings(test_database_url):
    settings = Settings(
        _env_file=None, APP_ENV="testing", DEBUG=False, DATABASE_URL=TEST_DATABASE_URL
    )  # pyright: ignore[reportCallIssue]

    assert settings.APP_ENV == "testing"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == test_database_url


def test_missing_database_url_fails(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
