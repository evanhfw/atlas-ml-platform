from typing import override
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_ml_platform.modules.artifacts.application.ports import ArtifactRepository
from atlas_ml_platform.modules.artifacts.domain.artifact import Artifact
from atlas_ml_platform.modules.artifacts.infrastructure.records import ArtifactRecord


class SQLAlchemyArtifactRepository(ArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def add(self, artifact: Artifact) -> None:
        self._session.add(self._to_record(artifact))
        await self._session.flush()

    @override
    async def get(self, artifact_id: UUID) -> Artifact | None:
        record = await self._session.get(ArtifactRecord, artifact_id)
        return self._to_domain(record) if record is not None else None

    @override
    async def get_by_uri(self, uri: str) -> Artifact | None:
        result = await self._session.execute(
            select(ArtifactRecord).where(ArtifactRecord.uri == uri)
        )
        record = result.scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    @staticmethod
    def _to_domain(record: ArtifactRecord) -> Artifact:
        return Artifact(
            id=record.id,
            key=record.key,
            uri=record.uri,
            checksum=record.checksum,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
            created_at=record.created_at,
        )

    @staticmethod
    def _to_record(artifact: Artifact) -> ArtifactRecord:
        return ArtifactRecord(
            id=artifact.id,
            key=artifact.key,
            uri=artifact.uri,
            checksum=artifact.checksum,
            size_bytes=artifact.size_bytes,
            content_type=artifact.content_type,
            created_at=artifact.created_at,
        )
