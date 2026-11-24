import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self, override

from atlas_ml_platform.modules.model_registry.domain.errors import (
    InvalidArtifactUri,
    InvalidVersionNumber,
    InvalidVersionTransition,
)


class VersionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True, eq=False)
class ModelVersion:
    """An immutable model version with an explicit lifecycle."""

    id: uuid.UUID
    model_id: uuid.UUID
    version_number: int
    status: VersionStatus
    artifact_uri: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise InvalidVersionNumber("Version number must be at least 1")

        normalized_uri = self.artifact_uri.strip()
        if not normalized_uri:
            raise InvalidArtifactUri("Artifact URI must not be empty")

        object.__setattr__(self, "artifact_uri", normalized_uri)

    @classmethod
    def create(
        cls,
        *,
        model_id: uuid.UUID,
        version_number: int,
        artifact_uri: str,
    ) -> Self:
        now = datetime.now(UTC)
        return cls(
            id=uuid.uuid4(),
            model_id=model_id,
            version_number=version_number,
            status=VersionStatus.DRAFT,
            artifact_uri=artifact_uri,
            created_at=now,
            updated_at=now,
        )

    def mark_ready(self) -> Self:
        if self.status is not VersionStatus.DRAFT:
            raise InvalidVersionTransition(
                f"Cannot mark version {self.version_number} ready from {self.status.value}"
            )

        return replace(
            self,
            status=VersionStatus.READY,
            updated_at=datetime.now(UTC),
        )

    def archive(self) -> Self:
        if self.status is VersionStatus.ARCHIVED:
            raise InvalidVersionTransition("Version is already archived")

        return replace(
            self,
            status=VersionStatus.ARCHIVED,
            updated_at=datetime.now(UTC),
        )

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModelVersion):
            return NotImplemented
        return self.id == other.id

    @override
    def __hash__(self) -> int:
        return hash(self.id)
