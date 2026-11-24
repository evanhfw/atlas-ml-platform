import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self, override

from atlas_ml_platform.modules.artifacts.domain.errors import InvalidArtifact


@dataclass(frozen=True, slots=True, eq=False)
class Artifact:
    """Metadata for an immutable object stored in object storage."""

    id: uuid.UUID
    key: str
    uri: str
    checksum: str
    size_bytes: int
    content_type: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise InvalidArtifact("Artifact key must not be empty")
        if not self.uri.strip():
            raise InvalidArtifact("Artifact URI must not be empty")
        if len(self.checksum) != 64 or any(
            char not in "0123456789abcdef" for char in self.checksum
        ):
            raise InvalidArtifact("Artifact checksum must be a SHA-256 hex digest")
        if self.size_bytes <= 0:
            raise InvalidArtifact("Artifact size must be greater than zero")
        if not self.content_type.strip():
            raise InvalidArtifact("Artifact content type must not be empty")

    @classmethod
    def create(
        cls,
        *,
        id: uuid.UUID,
        key: str,
        uri: str,
        checksum: str,
        size_bytes: int,
        content_type: str,
    ) -> Self:
        return cls(
            id=id,
            key=key,
            uri=uri,
            checksum=checksum,
            size_bytes=size_bytes,
            content_type=content_type,
            created_at=datetime.now(UTC),
        )

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artifact):
            return NotImplemented
        return self.id == other.id

    @override
    def __hash__(self) -> int:
        return hash(self.id)
