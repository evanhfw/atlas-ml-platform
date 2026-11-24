from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from atlas_ml_platform.api.dependencies import UnitOfWorkDep
from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelCommand,
    ListModelsQuery,
)
from atlas_ml_platform.modules.model_registry.application.model_use_cases import (
    CreateModel,
    GetModel,
    ListModels,
)
from atlas_ml_platform.modules.model_registry.presentation.schemas import (
    ModelCreate,
    ModelList,
    ModelRead,
)
from atlas_ml_platform.modules.model_registry.presentation.version_routes import (
    router as version_router,
)

router = APIRouter(prefix="/models", tags=["models"])

router.include_router(version_router)


@router.post("", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
async def create_model(payload: ModelCreate, uow: UnitOfWorkDep) -> ModelRead:
    model = await CreateModel(uow).execute(
        CreateModelCommand(
            name=payload.name,
            description=payload.description,
            framework=payload.framework,
            task_type=payload.task_type,
        )
    )
    return ModelRead.from_domain(model)


@router.get("/{model_id}", response_model=ModelRead)
async def get_model(model_id: UUID, uow: UnitOfWorkDep) -> ModelRead:
    model = await GetModel(uow).execute(model_id)
    return ModelRead.from_domain(model)


@router.get("", response_model=ModelList)
async def list_models(
    uow: UnitOfWorkDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ModelList:
    models = await ListModels(uow).execute(ListModelsQuery(limit=limit, offset=offset))

    return ModelList(
        items=[ModelRead.from_domain(model) for model in models],
        limit=limit,
        offset=offset,
    )
