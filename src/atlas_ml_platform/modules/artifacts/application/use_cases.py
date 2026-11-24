import uuid
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID

from atlas_ml_platform.modules.artifacts.application.content import (
    read_verified_artifact,
)
from atlas_ml_platform.modules.artifacts.application.errors import (
    ArtifactNotFound,
    ArtifactTooLarge,
    UnsupportedArtifactType,
)
from atlas_ml_platform.modules.artifacts.application.limits import (
    ALLOWED_ARTIFACT_CONTENT_TYPES,
)
from atlas_ml_platform.modules.artifacts.application.ports import (
    ArtifactStore,
    ArtifactUnitOfWork,
)
from atlas_ml_platform.modules.artifacts.domain.artifact import Artifact
from atlas_ml_platform.modules.artifacts.domain.errors import InvalidArtifact


@dataclass(frozen=True, slots=True)
class UploadArtifactCommand:
    data: bytes
    content_type: str


class UploadArtifact:
    def __init__(
        self,
        uow: ArtifactUnitOfWork,
        store: ArtifactStore,
        *,
        max_size_bytes: int,
    ) -> None:
        self._uow = uow
        self._store = store
        self._max_size_bytes = max_size_bytes

    async def execute(self, command: UploadArtifactCommand) -> Artifact:
        content_type = command.content_type.split(";", 1)[0].strip().lower()
        if content_type not in ALLOWED_ARTIFACT_CONTENT_TYPES:
            raise UnsupportedArtifactType(content_type)
        if not command.data:
            raise InvalidArtifact("Artifact data must not be empty")
        if len(command.data) > self._max_size_bytes:
            raise ArtifactTooLarge(self._max_size_bytes)

        artifact_id = uuid.uuid4()
        key = f"artifacts/{artifact_id}"
        stored = await self._store.put(
            key=key,
            data=command.data,
            content_type=content_type,
        )
        artifact = Artifact.create(
            id=artifact_id,
            key=stored.key,
            uri=stored.uri,
            checksum=stored.checksum,
            size_bytes=stored.size_bytes,
            content_type=stored.content_type,
        )
        try:
            await self._uow.artifacts.add(artifact)
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            # Best-effort compensation; never mask the original persistence error.
            with suppress(Exception):
                await self._store.delete(key)
            raise
        return artifact


class GetArtifact:
    def __init__(self, uow: ArtifactUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, artifact_id: UUID) -> Artifact:
        artifact = await self._uow.artifacts.get(artifact_id)
        if artifact is None:
            raise ArtifactNotFound(artifact_id)
        return artifact


class DownloadArtifact:
    def __init__(self, uow: ArtifactUnitOfWork, store: ArtifactStore) -> None:
        self._uow = uow
        self._store = store

    async def execute(self, artifact_id: UUID) -> tuple[Artifact, bytes]:
        artifact = await self._uow.artifacts.get(artifact_id)
        if artifact is None:
            raise ArtifactNotFound(artifact_id)
        data = await read_verified_artifact(artifact, self._store)
        return artifact, data
