from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from atlas_ml_platform.api.dependencies import UnitOfWorkDep
from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelVersionCommand,
    ListModelVersionsQuery,
)
from atlas_ml_platform.modules.model_registry.application.version_use_cases import (
    ActivateModelVersion,
    CreateModelVersion,
    GetActiveModelVersion,
    GetModelVersion,
    ListModelVersions,
    MarkModelVersionReady,
)
from atlas_ml_platform.modules.model_registry.presentation.schemas import (
    ModelVersionCreate,
    ModelVersionList,
    ModelVersionRead,
)

router = APIRouter(prefix="/{model_id}/versions", tags=["versions"])


@router.post(
    "",
    response_model=ModelVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    model_id: UUID,
    payload: ModelVersionCreate,
    uow: UnitOfWorkDep,
) -> ModelVersionRead:
    version = await CreateModelVersion(uow).execute(
        CreateModelVersionCommand(
            model_id=model_id,
            artifact_uri=payload.artifact_uri,
        )
    )
    return ModelVersionRead.from_domain(version)


@router.get("", response_model=ModelVersionList)
async def list_versions(
    model_id: UUID,
    uow: UnitOfWorkDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ModelVersionList:
    versions = await ListModelVersions(uow).execute(
        model_id,
        ListModelVersionsQuery(limit=limit, offset=offset),
    )

    return ModelVersionList(
        items=[ModelVersionRead.from_domain(version) for version in versions],
        limit=limit,
        offset=offset,
    )


@router.get("/active", response_model=ModelVersionRead)
async def get_active_version(
    model_id: UUID,
    uow: UnitOfWorkDep,
) -> ModelVersionRead:
    version = await GetActiveModelVersion(uow).execute(model_id)
    return ModelVersionRead.from_domain(version)


@router.get("/{version_id}", response_model=ModelVersionRead)
async def get_version(
    model_id: UUID,
    version_id: UUID,
    uow: UnitOfWorkDep,
) -> ModelVersionRead:
    version = await GetModelVersion(uow).execute(model_id, version_id)
    return ModelVersionRead.from_domain(version)


@router.post("/{version_id}/ready", response_model=ModelVersionRead)
async def mark_version_ready(
    model_id: UUID,
    version_id: UUID,
    uow: UnitOfWorkDep,
) -> ModelVersionRead:
    version = await MarkModelVersionReady(uow).execute(model_id, version_id)
    return ModelVersionRead.from_domain(version)


@router.post("/{version_id}/activate", response_model=ModelVersionRead)
async def activate_version(
    model_id: UUID,
    version_id: UUID,
    uow: UnitOfWorkDep,
) -> ModelVersionRead:
    version = await ActivateModelVersion(uow).execute(model_id, version_id)
    return ModelVersionRead.from_domain(version)
