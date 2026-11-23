import logging

from fastapi.testclient import TestClient

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app


def test_application_lifespan(caplog):
    settings = Settings(_env_file=None, APP_ENV="testing", DEBUG=False)  # pyright: ignore[reportCallIssue]

    app = create_app(settings=settings)

    with caplog.at_level(logging.INFO), TestClient(app):
        pass

    assert "Starting Atlas ML Platform in testing mode" in caplog.text
    assert "Shutting down Atlas ML Platform" in caplog.text
