import hashlib
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from botocore.exceptions import ClientError

from atlas_ml_platform.modules.artifacts.infrastructure import S3ArtifactStore


@pytest_asyncio.fixture
async def artifact_store() -> S3ArtifactStore:
    return await S3ArtifactStore.create(
        endpoint=os.environ.get("S3_ENDPOINT", "localhost:8333"),
        access_key=os.environ.get("S3_ACCESS_KEY", "atlas"),
        secret_key=os.environ.get("S3_SECRET_KEY", "atlas_s3_password"),
        bucket="atlas-models-test",
        region=os.environ.get("S3_REGION", "us-east-1"),
        secure=False,
    )


async def test_put_get_delete_round_trip(
    artifact_store: S3ArtifactStore,
) -> None:
    key = f"tests/{uuid4()}.joblib"
    data = b"model-bytes" * 1024

    stored = await artifact_store.put(
        key=key,
        data=data,
        content_type="application/octet-stream",
    )

    assert stored.key == key
    assert stored.uri == f"s3://atlas-models-test/{key}"
    assert stored.checksum == hashlib.sha256(data).hexdigest()
    assert stored.size_bytes == len(data)

    try:
        assert await artifact_store.get(key) == data
    finally:
        await artifact_store.delete(key)

    with pytest.raises(ClientError):
        _ = await artifact_store.get(key)
