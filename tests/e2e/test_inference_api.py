import asyncio
import hashlib
import io
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import httpx
import joblib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app
from atlas_ml_platform.core.logging import JsonFormatter

ARTIFACTS_URL = "/api/v1/artifacts"
MODELS_URL = "/api/v1/models"
INFERENCE_LOGGER = "atlas_ml_platform.modules.inference.application.use_cases"

IRIS_ROWS = [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 4.4, 1.4]]
IRIS_LABELS = [0, 1]
DISTINCTIVE_FEATURES = [[987654.125, 123456.25, 456789.5, 789123.75]]


@pytest.fixture(scope="session")
def iris_artifact_bytes() -> bytes:
    features, labels = load_iris(return_X_y=True)
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=0)),
        ]
    )
    model.fit(features, labels)

    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    return buffer.getvalue()


@pytest.fixture
def make_client(test_settings: Settings) -> Iterator[Callable[..., TestClient]]:
    with ExitStack() as stack:

        def _make(
            *,
            trusted_checksums: str = "",
            max_batch_size: int = 2,
            trust_policy: Literal["allowlist", "auto"] = "allowlist",
        ) -> TestClient:
            settings = Settings(
                _env_file=None,
                APP_ENV="testing",
                DEBUG=False,
                DATABASE_URL=test_settings.DATABASE_URL,
                S3_BUCKET="atlas-models-test",
                TRUSTED_ARTIFACT_CHECKSUMS=trusted_checksums,
                ARTIFACT_TRUST_POLICY=trust_policy,
                INFERENCE_MAX_BATCH_SIZE=max_batch_size,
            )
            return stack.enter_context(TestClient(create_app(settings=settings)))

        yield _make


@pytest.fixture
def upload() -> Iterator[Callable[..., dict]]:
    uploaded: list[tuple[TestClient, str]] = []

    def _upload(
        client: TestClient,
        data: bytes,
        content_type: str = "application/x-joblib",
    ) -> dict:
        response = client.post(
            ARTIFACTS_URL,
            files={"file": ("model.joblib", data, content_type)},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        uploaded.append((client, f"artifacts/{body['id']}"))
        return body

    yield _upload

    for client, key in uploaded:
        store = cast(FastAPI, client.app).state.artifact_store
        asyncio.run(store.delete(key))


def _create_model(client: TestClient) -> dict:
    response = client.post(
        MODELS_URL,
        json={
            "name": f"iris-{uuid4().hex[:8]}",
            "description": "Iris classifier",
            "framework": "sklearn",
            "task_type": "classification",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_version(client: TestClient, model_id: str, artifact_uri: str) -> dict:
    response = client.post(
        f"{MODELS_URL}/{model_id}/versions",
        json={"artifact_uri": artifact_uri},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _activate(client: TestClient, model_id: str, version_id: str) -> None:
    base = f"{MODELS_URL}/{model_id}/versions/{version_id}"
    ready = client.post(f"{base}/ready")
    assert ready.status_code == 200, ready.text
    activated = client.post(f"{base}/activate")
    assert activated.status_code == 200, activated.text


def _deploy(
    client: TestClient,
    upload: Callable[..., dict],
    data: bytes,
    *,
    activate: bool = True,
) -> tuple[dict, dict, dict]:
    artifact = upload(client, data)
    model = _create_model(client)
    version = _create_version(client, model["id"], artifact["uri"])
    if activate:
        _activate(client, model["id"], version["id"])
    return artifact, model, version


@pytest.fixture
def deployed_iris(
    make_client: Callable[..., TestClient],
    upload: Callable[..., dict],
    iris_artifact_bytes: bytes,
) -> tuple[TestClient, dict, dict]:
    client = make_client(
        trusted_checksums=hashlib.sha256(iris_artifact_bytes).hexdigest()
    )
    _, model, version = _deploy(client, upload, iris_artifact_bytes)
    return client, model, version


def _predict(
    client: TestClient,
    model_id: str,
    features: object,
) -> httpx.Response:
    # json= refuses NaN; the API must still see and reject a non-finite value.
    return client.post(
        f"{MODELS_URL}/{model_id}/predictions",
        content=json.dumps({"features": features}),
        headers={"content-type": "application/json"},
    )


def test_predict_returns_exact_predictions_and_request_identity(
    deployed_iris: tuple[TestClient, dict, dict],
) -> None:
    client, model, version = deployed_iris

    response = _predict(client, model["id"], IRIS_ROWS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["predictions"] == IRIS_LABELS
    assert UUID(body["request_id"])
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["model_id"] == model["id"]
    assert body["model_version_id"] == version["id"]
    assert body["version_number"] == 1
    assert isinstance(body["latency_ms"], float)
    assert body["latency_ms"] >= 0.0

    second = _predict(client, model["id"], IRIS_ROWS)

    assert second.status_code == 200
    second_body = second.json()
    assert second_body["predictions"] == IRIS_LABELS
    assert second_body["request_id"] == second.headers["x-request-id"]
    assert second_body["request_id"] != body["request_id"]


@pytest.mark.parametrize(
    "features",
    [
        [],
        [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 1.4]],
        [[5.1, 3.5, 1.4, float("nan")]],
        [[5.1, 3.5, 1.4]],
        [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 4.4, 1.4], [6.3, 3.3, 6.0, 2.5]],
    ],
    ids=["empty", "ragged", "nan", "wrong-feature-count", "over-batch-limit"],
)
def test_invalid_inputs_return_422(
    deployed_iris: tuple[TestClient, dict, dict],
    features: object,
) -> None:
    client, model, _ = deployed_iris

    response = _predict(client, model["id"], features)

    assert response.status_code == 422, response.text


def test_untrusted_artifact_returns_500(
    make_client: Callable[..., TestClient],
    upload: Callable[..., dict],
    iris_artifact_bytes: bytes,
) -> None:
    client = make_client(trusted_checksums="")
    _, model, _ = _deploy(client, upload, iris_artifact_bytes)

    response = _predict(client, model["id"], IRIS_ROWS)

    assert response.status_code == 500, response.text
    assert "allowlist" in response.json()["detail"]


def test_trusted_but_invalid_artifact_returns_500(
    make_client: Callable[..., TestClient],
    upload: Callable[..., dict],
) -> None:
    garbage = b"not-a-joblib-artifact"
    client = make_client(trusted_checksums=hashlib.sha256(garbage).hexdigest())
    _, model, _ = _deploy(client, upload, garbage)

    response = _predict(client, model["id"], IRIS_ROWS)

    assert response.status_code == 500, response.text
    assert "deserialize" in response.json()["detail"]


def test_corrupted_object_returns_500(
    make_client: Callable[..., TestClient],
    upload: Callable[..., dict],
    iris_artifact_bytes: bytes,
) -> None:
    client = make_client(
        trusted_checksums=hashlib.sha256(iris_artifact_bytes).hexdigest()
    )
    artifact, model, _ = _deploy(client, upload, iris_artifact_bytes)
    store = cast(FastAPI, client.app).state.artifact_store
    _ = asyncio.run(
        store.put(
            key=f"artifacts/{artifact['id']}",
            data=b"x" * len(iris_artifact_bytes),
            content_type="application/x-joblib",
        )
    )

    response = _predict(client, model["id"], IRIS_ROWS)

    assert response.status_code == 500, response.text
    assert "checksum" in response.json()["detail"]


def test_missing_active_version_returns_404(
    make_client: Callable[..., TestClient],
    upload: Callable[..., dict],
    iris_artifact_bytes: bytes,
) -> None:
    client = make_client(
        trusted_checksums=hashlib.sha256(iris_artifact_bytes).hexdigest()
    )
    _, model, _ = _deploy(client, upload, iris_artifact_bytes, activate=False)

    response = _predict(client, model["id"], IRIS_ROWS)

    assert response.status_code == 404, response.text
    assert "active version" in response.json()["detail"].lower()


def test_auto_trust_policy_serves_artifact_missing_from_allowlist(
    make_client: Callable[..., TestClient],
    upload: Callable[..., dict],
    iris_artifact_bytes: bytes,
) -> None:
    client = make_client(trust_policy="auto", trusted_checksums="")
    _, model, _ = _deploy(client, upload, iris_artifact_bytes)

    response = _predict(client, model["id"], IRIS_ROWS)

    assert response.status_code == 200, response.text
    assert response.json()["predictions"] == IRIS_LABELS


def test_prediction_logs_metadata_without_feature_values(
    deployed_iris: tuple[TestClient, dict, dict],
    caplog,
) -> None:
    client, model, version = deployed_iris
    caplog.clear()
    with caplog.at_level(logging.INFO):
        response = _predict(client, model["id"], DISTINCTIVE_FEATURES)

    assert response.status_code == 200, response.text
    body = response.json()
    records = [
        record
        for record in caplog.records
        if record.name == INFERENCE_LOGGER
        and record.getMessage() == "inference_completed"
    ]
    assert len(records) == 1
    record = cast(Any, records[0])
    assert record.model_id == model["id"]
    assert record.version_id == version["id"]
    assert record.rows == 1
    assert record.outcome == "success"
    assert isinstance(record.latency_ms, float)
    assert record.latency_ms >= 0.0
    assert str(record.request_id) == response.headers["x-request-id"]
    assert str(record.request_id) == body["request_id"]

    emitted = JsonFormatter(service="atlas-test", environment="testing").format(record)
    payload = json.loads(emitted)
    assert payload["message"] == "inference_completed"
    for raw_value in ("987654.125", "123456.25", "456789.5", "789123.75"):
        assert raw_value not in emitted
        assert raw_value not in caplog.text
