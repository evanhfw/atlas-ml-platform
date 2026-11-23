from fastapi.testclient import TestClient

from atlas_ml_platform.core.application import create_app


def test_health_check(test_settings):
    app = create_app(settings=test_settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "atlas-ml-platform"}


def test_database_health(test_settings):
    app = create_app(settings=test_settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}
