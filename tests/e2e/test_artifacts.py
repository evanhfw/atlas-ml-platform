import asyncio
import hashlib
from collections.abc import Callable, Iterator
from typing import cast
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app

ARTIFACTS_URL = "/api/v1/artifacts"


@pytest.fixture
def upload(
    client: TestClient,
) -> Iterator[Callable[[bytes, str], httpx.Response]]:
    uploaded_keys: list[str] = []

    def _upload(
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> httpx.Response:
        response = client.post(
            ARTIFACTS_URL,
            files={"file": ("model.bin", data, content_type)},
        )
        if response.status_code == 201:
            uploaded_keys.append(f"artifacts/{response.json()['id']}")
        return response

    yield _upload

    store = cast(FastAPI, client.app).state.artifact_store
    for key in uploaded_keys:
        asyncio.run(store.delete(key))


@pytest.fixture
def small_limit_client(test_settings: Settings) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        DEBUG=False,
        DATABASE_URL=test_settings.DATABASE_URL,
        S3_BUCKET="atlas-models-test",
        ARTIFACT_MAX_SIZE_BYTES=8,
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_upload_get_and_download_round_trip(
    client: TestClient,
    upload: Callable[[bytes, str], httpx.Response],
) -> None:
    data = bytes(range(256)) * 3

    created = upload(data, "application/octet-stream")

    assert created.status_code == 201
    body = created.json()
    artifact_id = body["id"]
    assert body["checksum"] == hashlib.sha256(data).hexdigest()
    assert body["size_bytes"] == len(data)
    assert body["content_type"] == "application/octet-stream"
    assert body["uri"] == f"s3://atlas-models-test/artifacts/{artifact_id}"
    assert body["created_at"]

    fetched = client.get(f"{ARTIFACTS_URL}/{artifact_id}")

    assert fetched.status_code == 200
    assert fetched.json() == body

    downloaded = client.get(f"{ARTIFACTS_URL}/{artifact_id}/content")

    assert downloaded.status_code == 200
    assert downloaded.content == data
    assert downloaded.headers["content-type"] == "application/octet-stream"
    assert artifact_id in downloaded.headers["content-disposition"]


def test_upload_rejects_unsupported_content_type(
    upload: Callable[[bytes, str], httpx.Response],
) -> None:
    response = upload(b"data", "text/plain")

    assert response.status_code == 415
    assert "unsupported" in response.json()["detail"].lower()


def test_missing_artifact_returns_404(client: TestClient) -> None:
    missing = uuid4()

    metadata = client.get(f"{ARTIFACTS_URL}/{missing}")
    content = client.get(f"{ARTIFACTS_URL}/{missing}/content")

    assert metadata.status_code == 404
    assert content.status_code == 404


def test_download_detects_corrupted_object(
    client: TestClient,
    upload: Callable[[bytes, str], httpx.Response],
) -> None:
    data = b"trusted-model-bytes"
    created = upload(data)
    assert created.status_code == 201
    artifact_id = created.json()["id"]
    store = cast(FastAPI, client.app).state.artifact_store
    _ = asyncio.run(
        store.put(
            key=f"artifacts/{artifact_id}",
            data=b"x" * len(data),
            content_type="application/octet-stream",
        )
    )

    response = client.get(f"{ARTIFACTS_URL}/{artifact_id}/content")

    assert response.status_code == 500
    assert "checksum" in response.json()["detail"].lower()


def test_upload_over_limit_returns_413(
    small_limit_client: TestClient,
) -> None:
    response = small_limit_client.post(
        ARTIFACTS_URL,
        files={"file": ("model.bin", b"123456789", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert "maximum" in response.json()["detail"].lower()
