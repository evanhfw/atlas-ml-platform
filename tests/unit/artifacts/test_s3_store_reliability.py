from typing import Any, cast

import boto3  # type: ignore[import-untyped]
import pytest

from atlas_ml_platform.modules.artifacts.infrastructure import S3ArtifactStore


class FakeS3Client:
    def __init__(self) -> None:
        self.head_bucket_calls: list[str] = []
        self.closed: bool = False
        self.created_buckets: list[str] = []

    def head_bucket(self, *, Bucket: str) -> None:
        self.head_bucket_calls.append(Bucket)

    def create_bucket(self, *, Bucket: str) -> None:
        self.created_buckets.append(Bucket)

    def close(self) -> None:
        self.closed = True


async def test_healthcheck_probes_the_configured_bucket() -> None:
    client = FakeS3Client()
    store = S3ArtifactStore(cast(Any, client), "models")

    await store.healthcheck()

    assert client.head_bucket_calls == ["models"]


async def test_close_closes_the_underlying_client() -> None:
    client = FakeS3Client()
    store = S3ArtifactStore(cast(Any, client), "models")

    await store.close()

    assert client.closed is True


async def test_create_applies_timeout_retry_and_endpoint_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeS3Client()
    captured: dict[str, Any] = {}

    def fake_client(service_name: str, **kwargs: Any) -> FakeS3Client:
        captured["service_name"] = service_name
        captured.update(kwargs)
        return client

    monkeypatch.setattr(boto3, "client", fake_client)

    _store = await S3ArtifactStore.create(
        endpoint="minio:9000",
        access_key="access",
        secret_key="secret",
        bucket="models",
        region="eu-west-1",
        secure=True,
        connect_timeout_seconds=1.25,
        read_timeout_seconds=7.5,
        max_attempts=5,
    )

    config = cast(Any, captured["config"])
    assert config.connect_timeout == 1.25
    assert config.read_timeout == 7.5
    assert config.retries == {"max_attempts": 5, "mode": "standard"}
    assert config.s3 == {"addressing_style": "path"}
    assert captured["endpoint_url"] == "https://minio:9000"
    assert captured["region_name"] == "eu-west-1"
    assert client.head_bucket_calls == ["models"]
