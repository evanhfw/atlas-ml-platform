import asyncio
import hashlib
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.modules.artifacts.domain import Artifact
from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelCommand,
    CreateModelVersionCommand,
    ListModelVersionsQuery,
)
from atlas_ml_platform.modules.model_registry.application.errors import (
    VersionNotReady,
)
from atlas_ml_platform.modules.model_registry.application.model_use_cases import (
    CreateModel,
)
from atlas_ml_platform.modules.model_registry.application.version_use_cases import (
    ActivateModelVersion,
    CreateModelVersion,
    GetActiveModelVersion,
    ListModelVersions,
    MarkModelVersionReady,
)
from atlas_ml_platform.modules.model_registry.domain import (
    Model,
    ModelVersion,
    VersionStatus,
)
from atlas_ml_platform.modules.model_registry.infrastructure import (
    SQLAlchemyUnitOfWork,
)


async def _create_model(
    session_factory: async_sessionmaker[AsyncSession],
    name: str = "churn",
) -> Model:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        return await CreateModel(uow).execute(
            CreateModelCommand(
                name=name,
                framework="sklearn",
                task_type="classification",
            )
        )


async def _register_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    uri: str = "s3://bucket/model.joblib",
) -> Artifact:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        existing = await uow.artifacts.get_by_uri(uri)
        if existing is not None:
            return existing

        artifact = Artifact.create(
            id=uuid4(),
            key=f"artifacts/{uuid4()}",
            uri=uri,
            checksum=hashlib.sha256(uri.encode()).hexdigest(),
            size_bytes=128,
            content_type="application/x-joblib",
        )
        await uow.artifacts.add(artifact)
        await uow.commit()
        return artifact


async def _create_version(
    session_factory: async_sessionmaker[AsyncSession],
    model_id: UUID,
    artifact_uri: str = "s3://bucket/model.joblib",
) -> ModelVersion:
    _ = await _register_artifact(session_factory, artifact_uri)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        return await CreateModelVersion(uow).execute(
            CreateModelVersionCommand(
                model_id=model_id,
                artifact_uri=artifact_uri,
            )
        )


async def test_create_versions_allocates_numbers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model = await _create_model(session_factory)

    first = await _create_version(session_factory, model.id)
    second = await _create_version(session_factory, model.id)

    assert first.version_number == 1
    assert second.version_number == 2
    assert first.status is VersionStatus.DRAFT
    assert second.status is VersionStatus.DRAFT

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        versions = await ListModelVersions(uow).execute(
            model.id,
            ListModelVersionsQuery(),
        )

    assert [version.version_number for version in versions] == [2, 1]


async def test_mark_ready_and_activate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model = await _create_model(session_factory)
    version = await _create_version(session_factory, model.id)

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        ready = await MarkModelVersionReady(uow).execute(model.id, version.id)

    assert ready.status is VersionStatus.READY

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        activated = await ActivateModelVersion(uow).execute(model.id, version.id)

    assert activated.id == version.id

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        active = await GetActiveModelVersion(uow).execute(model.id)

    assert active.id == version.id


async def test_activate_requires_ready_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model = await _create_model(session_factory)
    version = await _create_version(session_factory, model.id)

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        with pytest.raises(VersionNotReady):
            await ActivateModelVersion(uow).execute(model.id, version.id)


async def test_concurrent_version_creation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model = await _create_model(session_factory)
    artifact = await _register_artifact(session_factory)

    async def create() -> ModelVersion:
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            return await CreateModelVersion(uow).execute(
                CreateModelVersionCommand(
                    model_id=model.id,
                    artifact_uri=artifact.uri,
                )
            )

    first, second = await asyncio.gather(create(), create())

    assert {first.version_number, second.version_number} == {1, 2}


async def test_versions_are_scoped_per_model(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model_a = await _create_model(session_factory, "a")
    model_b = await _create_model(session_factory, "b")

    version_a = await _create_version(session_factory, model_a.id)
    version_b = await _create_version(session_factory, model_b.id)

    assert version_a.version_number == 1
    assert version_b.version_number == 1

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        versions = await ListModelVersions(uow).execute(
            model_a.id,
            ListModelVersionsQuery(),
        )

    assert [version.id for version in versions] == [version_a.id]


async def test_concurrent_activation_last_wins(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    model = await _create_model(session_factory)
    first = await _create_version(session_factory, model.id)
    second = await _create_version(session_factory, model.id)

    for version in (first, second):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            _ = await MarkModelVersionReady(uow).execute(model.id, version.id)

    async def activate(version_id: UUID) -> None:
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            _ = await ActivateModelVersion(uow).execute(model.id, version_id)

    _ = await asyncio.gather(activate(first.id), activate(second.id))

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        active = await GetActiveModelVersion(uow).execute(model.id)

    assert active.id in {first.id, second.id}
