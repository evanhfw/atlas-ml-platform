from fastapi.testclient import TestClient

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app


def test_documentation_routes_are_absent_when_docs_are_disabled(
    test_settings: Settings,
) -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        APP_ENV="testing",
        DEBUG=False,
        DATABASE_URL=test_settings.DATABASE_URL,
        S3_BUCKET="atlas-models-test",
        DOCS_ENABLED=False,
    )

    with TestClient(create_app(settings=settings)) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 404, path

        assert client.get("/api/v1/health").status_code == 200
