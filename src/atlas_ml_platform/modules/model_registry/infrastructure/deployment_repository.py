from typing import override
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_ml_platform.modules.model_registry.application.ports import (
    ModelDeploymentRepository,
)
from atlas_ml_platform.modules.model_registry.infrastructure.records import (
    ModelDeploymentRecord,
    ModelRecord,
)


class SQLAlchemyModelDeploymentRepository(ModelDeploymentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def get_active_version_id(self, model_id: UUID) -> UUID | None:
        result = await self._session.execute(
            select(ModelDeploymentRecord.version_id).where(
                ModelDeploymentRecord.model_id == model_id
            )
        )
        return result.scalar_one_or_none()

    @override
    async def activate(self, model_id: UUID, version_id: UUID) -> None:
        await self._session.execute(
            select(ModelRecord.id).where(ModelRecord.id == model_id).with_for_update()
        )

        statement = insert(ModelDeploymentRecord).values(
            model_id=model_id,
            version_id=version_id,
            updated_at=func.now(),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ModelDeploymentRecord.model_id],
            set_={
                "version_id": statement.excluded.version_id,
                "updated_at": func.now(),
            },
        )
        _ = await self._session.execute(statement)
