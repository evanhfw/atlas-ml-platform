from typing import override
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_ml_platform.modules.model_registry.application.errors import (
    VersionNumberConflict,
)
from atlas_ml_platform.modules.model_registry.application.ports import (
    ModelVersionRepository,
)
from atlas_ml_platform.modules.model_registry.domain import (
    ModelVersion,
    VersionStatus,
)
from atlas_ml_platform.modules.model_registry.infrastructure.records import (
    ModelRecord,
    ModelVersionRecord,
)


class SQLAlchemyModelVersionRepository(ModelVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def add(self, version: ModelVersion) -> None:
        self._session.add(self._to_record(version))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            original = exc.orig
            if (
                original is not None
                and "uq_model_versions_model_id_version_number" in str(original)
            ):
                raise VersionNumberConflict(version.model_id) from exc
            raise

    @override
    async def get(
        self,
        model_id: UUID,
        version_id: UUID,
    ) -> ModelVersion | None:
        result = await self._session.execute(
            select(ModelVersionRecord).where(
                ModelVersionRecord.id == version_id,
                ModelVersionRecord.model_id == model_id,
            )
        )
        record = result.scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    @override
    async def list_versions(
        self,
        *,
        model_id: UUID,
        limit: int,
        offset: int,
    ) -> list[ModelVersion]:
        result = await self._session.execute(
            select(ModelVersionRecord)
            .where(ModelVersionRecord.model_id == model_id)
            .order_by(ModelVersionRecord.version_number.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_domain(record) for record in result.scalars().all()]

    @override
    async def next_version_number(self, model_id: UUID) -> int:
        await self._session.execute(
            select(ModelRecord.id).where(ModelRecord.id == model_id).with_for_update()
        )
        result = await self._session.execute(
            select(func.coalesce(func.max(ModelVersionRecord.version_number), 0)).where(
                ModelVersionRecord.model_id == model_id
            )
        )
        return int(result.scalar_one()) + 1

    @override
    async def save(self, version: ModelVersion) -> None:
        record = await self._session.get(ModelVersionRecord, version.id)
        if record is None:
            raise RuntimeError(f"Model version {version.id} does not exist")

        record.status = version.status.value
        record.updated_at = version.updated_at
        await self._session.flush()

    @staticmethod
    def _to_domain(record: ModelVersionRecord) -> ModelVersion:
        return ModelVersion(
            id=record.id,
            model_id=record.model_id,
            version_number=record.version_number,
            status=VersionStatus(record.status),
            artifact_uri=record.artifact_uri,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _to_record(version: ModelVersion) -> ModelVersionRecord:
        return ModelVersionRecord(
            id=version.id,
            model_id=version.model_id,
            version_number=version.version_number,
            status=version.status.value,
            artifact_uri=version.artifact_uri,
            created_at=version.created_at,
            updated_at=version.updated_at,
        )
