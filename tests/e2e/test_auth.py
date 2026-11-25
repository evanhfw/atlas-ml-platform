from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app

MODELS_URL = "/api/v1/models"
READ_API_KEY = "read-key-" + "a" * 32
WRITE_API_KEY = "write-key-" + "b" * 32


def _model_payload() -> dict[str, str]:
    return {
        "name": "churn",
        "description": "Predict churn",
        "framework": "sklearn",
        "task_type": "classification",
    }


@pytest.fixture
def auth_client(test_settings: Settings) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        APP_ENV="testing",
        DEBUG=False,
        DATABASE_URL=test_settings.DATABASE_URL,
        S3_BUCKET="atlas-models-test",
        AUTH_ENABLED=True,
        API_KEY_READ=READ_API_KEY,
        API_KEY_WRITE=WRITE_API_KEY,
    )
    with TestClient(create_app(settings=settings)) as client:
        yield client


def test_health_and_metrics_are_reachable_without_api_key(
    auth_client: TestClient,
) -> None:
    health = auth_client.get("/api/v1/health")
    metrics = auth_client.get("/metrics")

    assert health.status_code == 200
    assert metrics.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-API-Key": "not-a-valid-key"}],
    ids=["missing", "invalid"],
)
def test_api_request_without_valid_key_is_rejected(
    auth_client: TestClient,
    headers: dict[str, str],
) -> None:
    response = auth_client.get(MODELS_URL, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"
    request_id = response.headers["x-request-id"]
    assert UUID(request_id)
    body = response.json()
    assert body["error_code"] == "unauthorized"
    assert body["request_id"] == request_id


def test_read_key_can_perform_read_requests(auth_client: TestClient) -> None:
    response = auth_client.get(
        MODELS_URL,
        headers={"X-API-Key": READ_API_KEY},
    )

    assert response.status_code == 200


def test_read_key_cannot_mutate_registry(auth_client: TestClient) -> None:
    response = auth_client.post(
        MODELS_URL,
        json=_model_payload(),
        headers={"X-API-Key": READ_API_KEY},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "forbidden"


def test_write_key_can_mutate_registry(auth_client: TestClient) -> None:
    response = auth_client.post(
        MODELS_URL,
        json=_model_payload(),
        headers={"X-API-Key": WRITE_API_KEY},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "churn"


def test_read_key_may_submit_predictions(auth_client: TestClient) -> None:
    response = auth_client.post(
        f"{MODELS_URL}/{uuid4()}/predictions",
        json={"features": [[1.0]]},
        headers={"X-API-Key": READ_API_KEY},
    )

    assert response.status_code == 404


def test_disabled_auth_accepts_requests_without_or_with_any_key(
    client: TestClient,
) -> None:
    without_key = client.get(MODELS_URL)
    with_bogus_key = client.get(
        MODELS_URL,
        headers={"X-API-Key": "not-a-real-key"},
    )

    assert without_key.status_code == 200
    assert with_bogus_key.status_code == 200
