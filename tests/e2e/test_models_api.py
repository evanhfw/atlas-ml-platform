import asyncio
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from atlas_ml_platform.core.application import create_app
from atlas_ml_platform.infrastructure.database.engine import create_database_engine


@pytest.fixture(autouse=True)
def clean_models(test_database_url: str) -> Iterator[None]:
    async def truncate() -> None:
        engine = create_database_engine(test_database_url)
        try:
            async with engine.begin() as connection:
                _ = await connection.execute(text("TRUNCATE TABLE models"))
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


def _payload(name: str = "churn") -> dict[str, str]:
    return {
        "name": name,
        "description": "Predict churn",
        "framework": "sklearn",
        "task_type": "classification",
    }


def test_create_model(client: TestClient) -> None:
    response = client.post("/api/v1/models", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "churn"
    assert body["description"] == "Predict churn"
    assert body["framework"] == "sklearn"
    assert body["task_type"] == "classification"
    _ = UUID(body["id"])
    assert body["created_at"]
    assert body["updated_at"]


def test_create_trims_name(client: TestClient) -> None:
    response = client.post("/api/v1/models", json=_payload("  churn  "))

    assert response.status_code == 201
    assert response.json()["name"] == "churn"


def test_get_model(client: TestClient) -> None:
    created = client.post("/api/v1/models", json=_payload()).json()

    response = client.get(f"/api/v1/models/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_model_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/models/{uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_duplicate_name_returns_409(client: TestClient) -> None:
    assert client.post("/api/v1/models", json=_payload()).status_code == 201

    response = client.post("/api/v1/models", json=_payload())

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_invalid_model_name_returns_422(client: TestClient) -> None:
    payload = _payload()
    payload["name"] = "bad\x00name"

    response = client.post("/api/v1/models", json=payload)

    assert response.status_code == 422


def test_unknown_field_returns_422(client: TestClient) -> None:
    payload = _payload()
    payload["unexpected"] = "value"

    response = client.post("/api/v1/models", json=payload)

    assert response.status_code == 422


def test_list_models_pagination(client: TestClient) -> None:
    for name in ("a", "b", "c"):
        assert client.post("/api/v1/models", json=_payload(name)).status_code == 201

    response = client.get(
        "/api/v1/models",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


def test_invalid_pagination_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/models", params={"limit": 0})

    assert response.status_code == 422
