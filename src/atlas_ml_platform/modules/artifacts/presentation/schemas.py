from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel

from atlas_ml_platform.modules.artifacts.domain import Artifact


class ArtifactRead(BaseModel):
    id: UUID
    uri: str
    checksum: str
    size_bytes: int
    content_type: str
    created_at: datetime

    @classmethod
    def from_domain(cls, artifact: Artifact) -> Self:
        return cls(
            id=artifact.id,
            uri=artifact.uri,
            checksum=artifact.checksum,
            size_bytes=artifact.size_bytes,
            content_type=artifact.content_type,
            created_at=artifact.created_at,
        )
