import asyncio
import hashlib
from collections.abc import Callable, Iterator
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ARTIFACTS_URL = "/api/v1/artifacts"


@pytest.fixture
def upload(client: TestClient) -> Iterator[Callable[[bytes, str], dict]]:
    uploaded_keys: list[str] = []

    def _upload(
        data: bytes = b"model-bytes",
        content_type: str = "application/x-joblib",
    ) -> dict:
        response = client.post(
            ARTIFACTS_URL,
            files={"file": ("model.joblib", data, content_type)},
        )
        assert response.status_code == 201
        body = response.json()
        uploaded_keys.append(f"artifacts/{body['id']}")
        return body

    yield _upload

    store = cast(FastAPI, client.app).state.artifact_store
    for key in uploaded_keys:
        asyncio.run(store.delete(key))


def _create_model(client: TestClient, name: str = "churn") -> dict:
    response = client.post(
        "/api/v1/models",
        json={
            "name": name,
            "description": "Predict churn",
            "framework": "sklearn",
            "task_type": "classification",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_version(
    client: TestClient,
    model_id: str,
    artifact_uri: str,
) -> dict:
    response = client.post(
        f"/api/v1/models/{model_id}/versions",
        json={"artifact_uri": artifact_uri},
    )
    assert response.status_code == 201
    return response.json()


def test_create_version(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    data = b"joblib-model-bytes"
    artifact = upload(data, "application/x-joblib")

    response = client.post(
        f"/api/v1/models/{model['id']}/versions",
        json={"artifact_uri": artifact["uri"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["status"] == "draft"
    assert body["artifact_uri"] == artifact["uri"]
    assert body["model_id"] == model["id"]
    _ = UUID(body["id"])
    assert body["artifact"] == {
        "id": artifact["id"],
        "uri": artifact["uri"],
        "checksum": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "content_type": "application/x-joblib",
        "created_at": artifact["created_at"],
    }


def test_create_versions_increments_number(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    artifact = upload()

    first = _create_version(client, model["id"], artifact["uri"])
    second = _create_version(client, model["id"], artifact["uri"])

    assert first["version_number"] == 1
    assert second["version_number"] == 2


def test_list_versions_pagination(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    artifact = upload()
    for _ in range(3):
        _ = _create_version(client, model["id"], artifact["uri"])

    response = client.get(
        f"/api/v1/models/{model['id']}/versions",
        params={"limit": 2, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["version_number"] for item in body["items"]] == [3, 2]


def test_get_version(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    data = b"onnx-weights"
    artifact = upload(data, "application/onnx")
    version = _create_version(client, model["id"], artifact["uri"])

    response = client.get(f"/api/v1/models/{model['id']}/versions/{version['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == version["id"]
    assert body["artifact"] == {
        "id": artifact["id"],
        "uri": artifact["uri"],
        "checksum": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "content_type": "application/onnx",
        "created_at": artifact["created_at"],
    }


def test_get_missing_version_returns_404(client: TestClient) -> None:
    model = _create_model(client)

    response = client.get(f"/api/v1/models/{model['id']}/versions/{uuid4()}")

    assert response.status_code == 404


def test_create_version_for_missing_model_returns_404(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    artifact = upload()

    response = client.post(
        f"/api/v1/models/{uuid4()}/versions",
        json={"artifact_uri": artifact["uri"]},
    )

    assert response.status_code == 404


def test_create_version_with_unregistered_artifact_returns_404(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    registered = upload()
    unregistered = f"{registered['uri']}-missing"

    response = client.post(
        f"/api/v1/models/{model['id']}/versions",
        json={"artifact_uri": unregistered},
    )

    assert response.status_code == 404
    assert unregistered in response.json()["detail"]

    listed = client.get(f"/api/v1/models/{model['id']}/versions")
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    created = _create_version(client, model["id"], registered["uri"])
    assert created["version_number"] == 1


def test_mark_ready_and_activate(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    artifact = upload()
    version = _create_version(client, model["id"], artifact["uri"])

    ready = client.post(f"/api/v1/models/{model['id']}/versions/{version['id']}/ready")
    activated = client.post(
        f"/api/v1/models/{model['id']}/versions/{version['id']}/activate"
    )
    active = client.get(f"/api/v1/models/{model['id']}/versions/active")

    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert activated.status_code == 200
    assert active.status_code == 200
    assert active.json()["id"] == version["id"]


def test_activate_draft_returns_409(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    artifact = upload()
    version = _create_version(client, model["id"], artifact["uri"])

    response = client.post(
        f"/api/v1/models/{model['id']}/versions/{version['id']}/activate"
    )

    assert response.status_code == 409
    assert "not ready" in response.json()["detail"].lower()


def test_mark_ready_twice_returns_409(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client)
    artifact = upload()
    version = _create_version(client, model["id"], artifact["uri"])
    url = f"/api/v1/models/{model['id']}/versions/{version['id']}/ready"
    assert client.post(url).status_code == 200

    response = client.post(url)

    assert response.status_code == 409


def test_get_active_without_deployment_returns_404(client: TestClient) -> None:
    model = _create_model(client)

    response = client.get(f"/api/v1/models/{model['id']}/versions/active")

    assert response.status_code == 404


def test_empty_artifact_uri_returns_422(client: TestClient) -> None:
    model = _create_model(client)

    response = client.post(
        f"/api/v1/models/{model['id']}/versions",
        json={"artifact_uri": ""},
    )

    assert response.status_code == 422


def test_versions_are_scoped_to_model(
    client: TestClient,
    upload: Callable[[bytes, str], dict],
) -> None:
    model = _create_model(client, "a")
    other = _create_model(client, "b")
    artifact = upload()
    version = _create_version(client, model["id"], artifact["uri"])

    response = client.get(f"/api/v1/models/{other['id']}/versions/{version['id']}")

    assert response.status_code == 404
