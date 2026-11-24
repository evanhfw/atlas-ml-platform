from datetime import UTC, datetime
from uuid import uuid4

import pytest

from atlas_ml_platform.modules.model_registry.domain import (
    InvalidArtifactUri,
    InvalidVersionNumber,
    InvalidVersionTransition,
    ModelVersion,
    VersionStatus,
)


def test_create_version_defaults_to_draft() -> None:
    model_id = uuid4()

    version = ModelVersion.create(
        model_id=model_id,
        version_number=1,
        artifact_uri="  s3://bucket/model.joblib  ",
    )

    assert version.model_id == model_id
    assert version.version_number == 1
    assert version.status is VersionStatus.DRAFT
    assert version.artifact_uri == "s3://bucket/model.joblib"
    assert version.created_at.tzinfo is not None
    assert version.created_at == version.updated_at


@pytest.mark.parametrize("version_number", [0, -1])
def test_invalid_version_number(version_number: int) -> None:
    with pytest.raises(InvalidVersionNumber):
        _ = ModelVersion.create(
            model_id=uuid4(),
            version_number=version_number,
            artifact_uri="s3://bucket/model.joblib",
        )


@pytest.mark.parametrize("artifact_uri", ["", "   "])
def test_invalid_artifact_uri(artifact_uri: str) -> None:
    with pytest.raises(InvalidArtifactUri):
        _ = ModelVersion.create(
            model_id=uuid4(),
            version_number=1,
            artifact_uri=artifact_uri,
        )


def test_mark_ready_transitions_draft() -> None:
    version = ModelVersion.create(
        model_id=uuid4(),
        version_number=1,
        artifact_uri="s3://bucket/model.joblib",
    )

    ready = version.mark_ready()

    assert ready.status is VersionStatus.READY
    assert ready.id == version.id
    assert ready.updated_at >= version.updated_at


def test_mark_ready_rejects_non_draft() -> None:
    version = ModelVersion.create(
        model_id=uuid4(),
        version_number=1,
        artifact_uri="s3://bucket/model.joblib",
    ).mark_ready()

    with pytest.raises(InvalidVersionTransition):
        _ = version.mark_ready()


def test_archive_from_draft() -> None:
    version = ModelVersion.create(
        model_id=uuid4(),
        version_number=1,
        artifact_uri="s3://bucket/model.joblib",
    )

    archived = version.archive()

    assert archived.status is VersionStatus.ARCHIVED


def test_archive_rejects_already_archived() -> None:
    archived = ModelVersion.create(
        model_id=uuid4(),
        version_number=1,
        artifact_uri="s3://bucket/model.joblib",
    ).archive()

    with pytest.raises(InvalidVersionTransition):
        _ = archived.archive()


def test_version_identity_is_based_on_id() -> None:
    version_id = uuid4()
    model_id = uuid4()
    now = datetime.now(UTC)

    first = ModelVersion(
        id=version_id,
        model_id=model_id,
        version_number=1,
        status=VersionStatus.DRAFT,
        artifact_uri="s3://bucket/first.joblib",
        created_at=now,
        updated_at=now,
    )
    second = ModelVersion(
        id=version_id,
        model_id=model_id,
        version_number=2,
        status=VersionStatus.ARCHIVED,
        artifact_uri="s3://bucket/second.joblib",
        created_at=now,
        updated_at=now,
    )

    assert first == second
    assert hash(first) == hash(second)
