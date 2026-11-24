from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.modules.artifacts.application.ports import ArtifactStore
from atlas_ml_platform.modules.inference.application.runtime_cache import (
    ModelRuntimeCache,
)
from atlas_ml_platform.modules.model_registry.infrastructure import (
    SQLAlchemyUnitOfWork,
)


async def get_unit_of_work(
    request: Request,
) -> AsyncIterator[SQLAlchemyUnitOfWork]:
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        yield uow


UnitOfWorkDep = Annotated[SQLAlchemyUnitOfWork, Depends(get_unit_of_work)]


def get_artifact_store(request: Request) -> ArtifactStore:
    return cast(ArtifactStore, request.app.state.artifact_store)


ArtifactStoreDep = Annotated[ArtifactStore, Depends(get_artifact_store)]


def get_model_runtime_cache(request: Request) -> ModelRuntimeCache:
    return cast(ModelRuntimeCache, request.app.state.model_runtime_cache)


ModelRuntimeCacheDep = Annotated[
    ModelRuntimeCache,
    Depends(get_model_runtime_cache),
]
