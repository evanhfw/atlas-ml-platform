import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app


@pytest.fixture
def dispose_calls(monkeypatch):
    calls = []
    original_dispose = AsyncEngine.dispose

    async def spy_dispose(self):
        calls.append(self)
        await original_dispose(self)

    monkeypatch.setattr(AsyncEngine, "dispose", spy_dispose)
    return calls


def test_application_lifespan(test_settings, caplog):
    app = create_app(settings=test_settings)

    with caplog.at_level(logging.INFO), TestClient(app):
        assert app.state.db_engine is not None
        assert app.state.session_factory is not None

    assert "Database connection established" in caplog.text
    assert "Shutting down Atlas ML Platform" in caplog.text


def test_shutdown_disposes_engine(dispose_calls, test_settings):
    app = create_app(settings=test_settings)

    with TestClient(app):
        pass

    assert len(dispose_calls) == 1


def test_startup_failure_disposes_engine(dispose_calls):
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL=(
            "postgresql+asyncpg://atlas:atlas_dev_password@127.0.0.1:1/atlas_test"
        ),
    )
    app = create_app(settings=settings)

    with pytest.raises(ConnectionRefusedError), TestClient(app):
        pass

    assert len(dispose_calls) == 1


def test_pool_size_comes_from_settings(test_database_url):
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL=test_database_url,
        DB_POOL_SIZE=3,
    )
    app = create_app(settings=settings)

    with TestClient(app):
        assert app.state.db_engine.pool.size() == 3
