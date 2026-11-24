from uuid import UUID, uuid4

from fastapi.testclient import TestClient


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
    artifact_uri: str = "s3://bucket/model.joblib",
) -> dict:
    response = client.post(
        f"/api/v1/models/{model_id}/versions",
        json={"artifact_uri": artifact_uri},
    )
    assert response.status_code == 201
    return response.json()


def test_create_version(client: TestClient) -> None:
    model = _create_model(client)

    response = client.post(
        f"/api/v1/models/{model['id']}/versions",
        json={"artifact_uri": "s3://bucket/model.joblib"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["status"] == "draft"
    assert body["artifact_uri"] == "s3://bucket/model.joblib"
    assert body["model_id"] == model["id"]
    _ = UUID(body["id"])


def test_create_versions_increments_number(client: TestClient) -> None:
    model = _create_model(client)

    first = _create_version(client, model["id"])
    second = _create_version(client, model["id"])

    assert first["version_number"] == 1
    assert second["version_number"] == 2


def test_list_versions_pagination(client: TestClient) -> None:
    model = _create_model(client)
    for _ in range(3):
        _ = _create_version(client, model["id"])

    response = client.get(
        f"/api/v1/models/{model['id']}/versions",
        params={"limit": 2, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["version_number"] for item in body["items"]] == [3, 2]


def test_get_version(client: TestClient) -> None:
    model = _create_model(client)
    version = _create_version(client, model["id"])

    response = client.get(f"/api/v1/models/{model['id']}/versions/{version['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == version["id"]


def test_get_missing_version_returns_404(client: TestClient) -> None:
    model = _create_model(client)

    response = client.get(f"/api/v1/models/{model['id']}/versions/{uuid4()}")

    assert response.status_code == 404


def test_create_version_for_missing_model_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/models/{uuid4()}/versions",
        json={"artifact_uri": "s3://bucket/model.joblib"},
    )

    assert response.status_code == 404


def test_mark_ready_and_activate(client: TestClient) -> None:
    model = _create_model(client)
    version = _create_version(client, model["id"])

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


def test_activate_draft_returns_409(client: TestClient) -> None:
    model = _create_model(client)
    version = _create_version(client, model["id"])

    response = client.post(
        f"/api/v1/models/{model['id']}/versions/{version['id']}/activate"
    )

    assert response.status_code == 409
    assert "not ready" in response.json()["detail"].lower()


def test_mark_ready_twice_returns_409(client: TestClient) -> None:
    model = _create_model(client)
    version = _create_version(client, model["id"])
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


def test_versions_are_scoped_to_model(client: TestClient) -> None:
    model = _create_model(client, "a")
    other = _create_model(client, "b")
    version = _create_version(client, model["id"])

    response = client.get(f"/api/v1/models/{other['id']}/versions/{version['id']}")

    assert response.status_code == 404
