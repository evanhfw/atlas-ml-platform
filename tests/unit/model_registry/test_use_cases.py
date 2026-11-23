from uuid import UUID, uuid4

import pytest

from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelCommand,
    ListModelsQuery,
)
from atlas_ml_platform.modules.model_registry.application.errors import (
    InvalidPagination,
    ModelNameAlreadyExists,
    ModelNotFound,
)
from atlas_ml_platform.modules.model_registry.application.ports import (
    ModelRepository,
)
from atlas_ml_platform.modules.model_registry.application.use_cases import (
    CreateModel,
    GetModel,
    ListModels,
)
from atlas_ml_platform.modules.model_registry.domain import Model, ModelName


class FakeModelRepository:
    def __init__(self) -> None:
        self._models: dict[UUID, Model] = {}

    async def add(self, model: Model) -> None:
        self._models[model.id] = model

    async def get(self, model_id: UUID) -> Model | None:
        return self._models.get(model_id)

    async def get_by_name(self, name: ModelName) -> Model | None:
        return next(
            (model for model in self._models.values() if model.name == name),
            None,
        )

    async def list_models(self, *, limit: int, offset: int) -> list[Model]:
        models = sorted(
            self._models.values(),
            key=lambda model: model.created_at,
            reverse=True,
        )
        return models[offset : offset + limit]


class FakeUnitOfWork:
    def __init__(self) -> None:
        self._models: FakeModelRepository = FakeModelRepository()
        self.committed: bool = False
        self.rolled_back: bool = False

    @property
    def models(self) -> ModelRepository:
        return self._models

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


async def test_create_model_persists_and_commits() -> None:
    uow = FakeUnitOfWork()

    model = await CreateModel(uow).execute(
        CreateModelCommand(
            name="  churn  ",
            description="Predict churn",
            framework="sklearn",
            task_type="classification",
        )
    )

    assert model.name.value == "churn"
    assert await uow.models.get(model.id) == model
    assert uow.committed is True
    assert uow.rolled_back is False


async def test_create_model_rejects_duplicate_name() -> None:
    uow = FakeUnitOfWork()
    use_case = CreateModel(uow)
    command = CreateModelCommand(
        name="churn",
        framework="sklearn",
        task_type="classification",
    )
    _ = await use_case.execute(command)

    with pytest.raises(ModelNameAlreadyExists):
        _ = await use_case.execute(
            CreateModelCommand(
                name="  churn  ",
                framework="sklearn",
                task_type="classification",
            )
        )

    assert uow.rolled_back is True


async def test_get_model_returns_entity() -> None:
    uow = FakeUnitOfWork()
    model = await CreateModel(uow).execute(
        CreateModelCommand(
            name="churn",
            framework="sklearn",
            task_type="classification",
        )
    )

    result = await GetModel(uow).execute(model.id)

    assert result == model


async def test_get_model_raises_when_missing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(ModelNotFound):
        _ = await GetModel(uow).execute(uuid4())


async def test_list_models_applies_pagination() -> None:
    uow = FakeUnitOfWork()
    create = CreateModel(uow)

    for name in ("a", "b", "c"):
        _ = await create.execute(
            CreateModelCommand(
                name=name,
                framework="sklearn",
                task_type="classification",
            )
        )

    page = await ListModels(uow).execute(ListModelsQuery(limit=2, offset=1))

    assert len(page) == 2


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (20, -1)],
)
async def test_list_models_rejects_invalid_pagination(
    limit: int,
    offset: int,
) -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(InvalidPagination):
        _ = await ListModels(uow).execute(ListModelsQuery(limit=limit, offset=offset))
