from uuid import UUID

from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelCommand,
    ListModelsQuery,
)
from atlas_ml_platform.modules.model_registry.application.errors import (
    ModelNameAlreadyExists,
    ModelNotFound,
)
from atlas_ml_platform.modules.model_registry.application.pagination import (
    validate_pagination,
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
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, query: ListModelsQuery) -> list[Model]:
        validate_pagination(limit=query.limit, offset=query.offset)

        return await self._uow.models.list_models(
            limit=query.limit,
            offset=query.offset,
        )
