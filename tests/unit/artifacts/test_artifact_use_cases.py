import hashlib
from uuid import uuid4

import pytest

from atlas_ml_platform.modules.artifacts.application import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactTooLarge,
    DownloadArtifact,
    UnsupportedArtifactType,
    UploadArtifact,
    UploadArtifactCommand,
)
from atlas_ml_platform.modules.artifacts.domain import Artifact, InvalidArtifact

MAX_SIZE_BYTES = 1024


def _seed_artifact(
    uow,
    store,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> Artifact:
    artifact_id = uuid4()
    key = f"artifacts/{artifact_id}"
    artifact = Artifact.create(
        id=artifact_id,
        key=key,
        uri=f"s3://test-bucket/{key}",
        checksum=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        content_type=content_type,
    )
    uow.artifacts.persisted[artifact.id] = artifact
    store.objects[key] = (data, content_type)
    return artifact


async def test_upload_stores_exact_bytes_and_persists_metadata(
    fake_uow,
    fake_store,
) -> None:
    data = b"\x00model-bytes\xff" * 4

    artifact = await UploadArtifact(
        fake_uow,
        fake_store,
        max_size_bytes=MAX_SIZE_BYTES,
    ).execute(UploadArtifactCommand(data=data, content_type="application/octet-stream"))

    assert fake_store.objects[artifact.key] == (data, "application/octet-stream")
    assert artifact.checksum == hashlib.sha256(data).hexdigest()
    assert artifact.size_bytes == len(data)
    assert artifact.content_type == "application/octet-stream"
    assert artifact.key == f"artifacts/{artifact.id}"
    assert artifact.uri == f"s3://test-bucket/artifacts/{artifact.id}"
    assert await fake_uow.artifacts.get(artifact.id) == artifact
    assert fake_uow.committed is True
    assert fake_uow.rolled_back is False


async def test_upload_normalizes_content_type_parameters(
    fake_uow,
    fake_store,
) -> None:
    artifact = await UploadArtifact(
        fake_uow,
        fake_store,
        max_size_bytes=MAX_SIZE_BYTES,
    ).execute(
        UploadArtifactCommand(
            data=b"archive",
            content_type="Application/Zip; charset=binary",
        )
    )

    assert artifact.content_type == "application/zip"
    assert fake_store.objects[artifact.key] == (b"archive", "application/zip")


async def test_upload_rejects_unsupported_content_type(
    fake_uow,
    fake_store,
) -> None:
    with pytest.raises(UnsupportedArtifactType) as exc_info:
        _ = await UploadArtifact(
            fake_uow,
            fake_store,
            max_size_bytes=MAX_SIZE_BYTES,
        ).execute(UploadArtifactCommand(data=b"data", content_type="text/plain"))

    assert exc_info.value.content_type == "text/plain"
    assert fake_store.put_keys == []
    assert fake_uow.committed is False


async def test_upload_rejects_data_over_limit(
    fake_uow,
    fake_store,
) -> None:
    with pytest.raises(ArtifactTooLarge) as exc_info:
        _ = await UploadArtifact(
            fake_uow,
            fake_store,
            max_size_bytes=8,
        ).execute(
            UploadArtifactCommand(
                data=b"123456789",
                content_type="application/octet-stream",
            )
        )

    assert exc_info.value.max_size_bytes == 8
    assert fake_store.put_keys == []
    assert fake_uow.committed is False


async def test_upload_accepts_data_exactly_at_limit(
    fake_uow,
    fake_store,
) -> None:
    data = b"12345678"

    artifact = await UploadArtifact(
        fake_uow,
        fake_store,
        max_size_bytes=8,
    ).execute(UploadArtifactCommand(data=data, content_type="application/octet-stream"))

    assert artifact.size_bytes == len(data)
    assert fake_store.objects[artifact.key] == (data, "application/octet-stream")


async def test_upload_rejects_empty_data(
    fake_uow,
    fake_store,
) -> None:
    with pytest.raises(InvalidArtifact):
        _ = await UploadArtifact(
            fake_uow,
            fake_store,
            max_size_bytes=MAX_SIZE_BYTES,
        ).execute(UploadArtifactCommand(data=b"", content_type="application/zip"))

    assert fake_store.put_keys == []
    assert fake_uow.committed is False


@pytest.mark.parametrize("failure_step", ["add", "commit"])
async def test_upload_compensates_when_persistence_fails(
    fake_uow,
    fake_store,
    failure_step: str,
) -> None:
    if failure_step == "add":
        fake_uow.artifacts.fail_add = True
    else:
        fake_uow.fail_commit = True

    with pytest.raises(RuntimeError, match=f"{failure_step} failed"):
        _ = await UploadArtifact(
            fake_uow,
            fake_store,
            max_size_bytes=MAX_SIZE_BYTES,
        ).execute(UploadArtifactCommand(data=b"data", content_type="application/zip"))

    assert fake_uow.rolled_back is True
    assert fake_uow.committed is False
    assert fake_uow.artifacts.persisted == {}
    assert fake_store.objects == {}
    assert fake_store.deleted == fake_store.put_keys
    assert len(fake_store.put_keys) == 1


async def test_download_returns_bytes_when_checksum_matches(
    fake_uow,
    fake_store,
) -> None:
    data = b"model-bytes"
    artifact = _seed_artifact(fake_uow, fake_store, data)

    returned, content = await DownloadArtifact(fake_uow, fake_store).execute(
        artifact.id
    )

    assert returned == artifact
    assert content == data


async def test_download_rejects_bytes_that_do_not_match_checksum(
    fake_uow,
    fake_store,
) -> None:
    data = b"trusted-bytes"
    artifact = _seed_artifact(fake_uow, fake_store, data)
    fake_store.objects[artifact.key] = (b"tampered-bytes", artifact.content_type)

    with pytest.raises(ArtifactIntegrityError) as exc_info:
        _ = await DownloadArtifact(fake_uow, fake_store).execute(artifact.id)

    assert exc_info.value.artifact_id == artifact.id


async def test_download_raises_not_found_when_metadata_is_missing(
    fake_uow,
    fake_store,
) -> None:
    artifact_id = uuid4()

    with pytest.raises(ArtifactNotFound) as exc_info:
        _ = await DownloadArtifact(fake_uow, fake_store).execute(artifact_id)

    assert exc_info.value.artifact_id == artifact_id
    assert fake_store.get_calls == 0
