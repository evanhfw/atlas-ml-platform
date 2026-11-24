from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.modules.model_registry.application.dto import CreateModelCommand
from atlas_ml_platform.modules.model_registry.application.errors import (
    ModelNameAlreadyExists,
)
from atlas_ml_platform.modules.model_registry.application.model_use_cases import (
    CreateModel,
)
from atlas_ml_platform.modules.model_registry.domain import Model, ModelName
from atlas_ml_platform.modules.model_registry.infrastructure import (
    SQLAlchemyUnitOfWork,
)


async def test_repository_round_trip(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model = Model.create(
        name=ModelName("  churn  "),
        description="Predict churn",
        framework="sklearn",
        task_type="classification",
    )

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.models.add(model)
        await uow.commit()
        fetched = await uow.models.get(model.id)
        by_name = await uow.models.get_by_name(ModelName("churn"))

    assert fetched is not None
    assert fetched.id == model.id
    assert fetched.name == model.name
    assert fetched.description == model.description
    assert fetched.framework == model.framework
    assert fetched.task_type == model.task_type
    assert fetched.created_at == model.created_at
    assert fetched.updated_at == model.updated_at

    assert by_name is not None
    assert by_name.id == model.id


async def test_get_missing_returns_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.models.get(uuid4()) is None
        assert await uow.models.get_by_name(ModelName("missing")) is None


async def test_list_models_newest_first(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    models = [
        Model(
            id=uuid4(),
            name=ModelName("oldest"),
            description=None,
            framework="sklearn",
            task_type="classification",
            created_at=base,
            updated_at=base,
        ),
        Model(
            id=uuid4(),
            name=ModelName("middle"),
            description=None,
            framework="sklearn",
            task_type="classification",
            created_at=base + timedelta(seconds=1),
            updated_at=base + timedelta(seconds=1),
        ),
        Model(
            id=uuid4(),
            name=ModelName("newest"),
            description=None,
            framework="sklearn",
            task_type="classification",
            created_at=base + timedelta(seconds=2),
            updated_at=base + timedelta(seconds=2),
        ),
    ]

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        for model in models:
            await uow.models.add(model)
        await uow.commit()

        page = await uow.models.list_models(limit=2, offset=0)
        next_page = await uow.models.list_models(limit=2, offset=2)

    assert [model.name.value for model in page] == ["newest", "middle"]
    assert [model.name.value for model in next_page] == ["oldest"]


async def test_duplicate_name_maps_to_application_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = Model.create(
        name=ModelName("churn"),
        framework="sklearn",
        task_type="classification",
    )
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.models.add(first)
        await uow.commit()

    duplicate = Model.create(
        name=ModelName("churn"),
        framework="sklearn",
        task_type="classification",
    )

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        with pytest.raises(ModelNameAlreadyExists):
            await uow.models.add(duplicate)
        await uow.rollback()

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        models = await uow.models.list_models(limit=10, offset=0)

    assert [model.id for model in models] == [first.id]


async def test_create_use_case_with_real_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        created = await CreateModel(uow).execute(
            CreateModelCommand(
                name="churn",
                description="Predict churn",
                framework="sklearn",
                task_type="classification",
            )
        )

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        fetched = await uow.models.get(created.id)

    assert fetched is not None
    assert fetched.name.value == "churn"
    assert fetched.description == "Predict churn"
