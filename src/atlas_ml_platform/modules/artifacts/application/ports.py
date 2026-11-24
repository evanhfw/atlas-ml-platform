from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from atlas_ml_platform.modules.artifacts.domain.artifact import Artifact


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    key: str
    uri: str
    checksum: str
    size_bytes: int
    content_type: str


class ArtifactStore(Protocol):
    """Contract for storing and retrieving model artifacts."""

    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredArtifact: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def healthcheck(self) -> None: ...


class ArtifactRepository(Protocol):
    """Persistence contract for immutable artifact metadata."""

    async def add(self, artifact: Artifact) -> None: ...

    async def get(self, artifact_id: UUID) -> Artifact | None: ...

    async def get_by_uri(self, uri: str) -> Artifact | None: ...


class ArtifactUnitOfWork(Protocol):
    @property
    def artifacts(self) -> ArtifactRepository: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
