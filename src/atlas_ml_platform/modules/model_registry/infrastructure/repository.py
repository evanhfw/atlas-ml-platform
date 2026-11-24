from typing import override
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_ml_platform.modules.model_registry.application.errors import (
    ModelNameAlreadyExists,
)
from atlas_ml_platform.modules.model_registry.application.ports import ModelRepository
from atlas_ml_platform.modules.model_registry.domain import Model, ModelName
from atlas_ml_platform.modules.model_registry.infrastructure.models import ModelRecord


class SQLAlchemyModelRepository(ModelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def add(self, model: Model) -> None:
        self._session.add(self._to_record(model))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _is_duplicate_model_name(exc):
                raise ModelNameAlreadyExists(model.name.value) from exc
            raise

    @override
    async def get(self, model_id: UUID) -> Model | None:
        record = await self._session.get(ModelRecord, model_id)
        return self._to_domain(record) if record is not None else None

    @override
    async def get_by_name(self, name: ModelName) -> Model | None:
        result = await self._session.execute(
            select(ModelRecord).where(ModelRecord.name == name.value)
        )
        record = result.scalar_one_or_none()
        return self._to_domain(record) if record is not None else None

    @override
    async def list_models(self, *, limit: int, offset: int) -> list[Model]:
        result = await self._session.execute(
            select(ModelRecord)
            .order_by(ModelRecord.created_at.desc(), ModelRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return [self._to_domain(record) for record in result.scalars().all()]

    @staticmethod
    def _to_domain(record: ModelRecord) -> Model:
        return Model(
            id=record.id,
            name=ModelName(record.name),
            description=record.description,
            framework=record.framework,
            task_type=record.task_type,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _to_record(model: Model) -> ModelRecord:
        return ModelRecord(
            id=model.id,
            name=model.name.value,
            description=model.description,
            framework=model.framework,
            task_type=model.task_type,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


def _is_duplicate_model_name(exc: IntegrityError) -> bool:
    original = exc.orig
    if original is None:
        return False
    return getattr(original, "sqlstate", None) == "23505" and "ix_models_name" in str(
        original
    )
