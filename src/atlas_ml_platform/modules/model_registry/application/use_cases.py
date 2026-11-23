from typing import ClassVar
from uuid import UUID

from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelCommand,
    ListModelsQuery,
)
from atlas_ml_platform.modules.model_registry.application.errors import (
    InvalidPagination,
    ModelNameAlreadyExists,
    ModelNotFound,
)
from atlas_ml_platform.modules.model_registry.application.ports import UnitOfWork
from atlas_ml_platform.modules.model_registry.domain import Model, ModelName


class CreateModel:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, command: CreateModelCommand) -> Model:
        name = ModelName(command.name)

        try:
            existing = await self._uow.models.get_by_name(name)
            if existing is not None:
                raise ModelNameAlreadyExists(name.value)

            model = Model.create(
                name=name,
                description=command.description,
                framework=command.framework,
                task_type=command.task_type,
            )
            await self._uow.models.add(model)
            await self._uow.commit()
            return model
        except Exception:
            await self._uow.rollback()
            raise


class GetModel:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, model_id: UUID) -> Model:
        model = await self._uow.models.get(model_id)
        if model is None:
            raise ModelNotFound(model_id)
        return model


class ListModels:
    MAX_LIMIT: ClassVar[int] = 100

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, query: ListModelsQuery) -> list[Model]:
        if not 1 <= query.limit <= self.MAX_LIMIT:
            raise InvalidPagination(f"limit must be between 1 and {self.MAX_LIMIT}")
        if query.offset < 0:
            raise InvalidPagination("offset must be greater than or equal to 0")

        return await self._uow.models.list_models(
            limit=query.limit,
            offset=query.offset,
        )
