from uuid import uuid4

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
from atlas_ml_platform.modules.model_registry.application.model_use_cases import (
    CreateModel,
    GetModel,
    ListModels,
)


async def test_create_model_persists_and_commits(fake_uow) -> None:
    uow = fake_uow

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


async def test_create_model_rejects_duplicate_name(fake_uow) -> None:
    uow = fake_uow
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


async def test_get_model_returns_entity(fake_uow) -> None:
    uow = fake_uow
    model = await CreateModel(uow).execute(
        CreateModelCommand(
            name="churn",
            framework="sklearn",
            task_type="classification",
        )
    )

    result = await GetModel(uow).execute(model.id)

    assert result == model


async def test_get_model_raises_when_missing(fake_uow) -> None:
    uow = fake_uow

    with pytest.raises(ModelNotFound):
        _ = await GetModel(uow).execute(uuid4())


async def test_list_models_applies_pagination(fake_uow) -> None:
    uow = fake_uow
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
    fake_uow,
    limit: int,
    offset: int,
) -> None:
    uow = fake_uow

    with pytest.raises(InvalidPagination):
        _ = await ListModels(uow).execute(ListModelsQuery(limit=limit, offset=offset))
