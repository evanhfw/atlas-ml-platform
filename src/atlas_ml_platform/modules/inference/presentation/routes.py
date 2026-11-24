from uuid import UUID

from fastapi import APIRouter, Request

from atlas_ml_platform.api.dependencies import (
    ArtifactStoreDep,
    ModelRuntimeCacheDep,
    UnitOfWorkDep,
)
from atlas_ml_platform.modules.inference.application.use_cases import RunInference
from atlas_ml_platform.modules.inference.presentation.schemas import (
    InferenceRequest,
    InferenceResponse,
)

router = APIRouter(prefix="/models/{model_id}/predictions", tags=["inference"])


@router.post("", response_model=InferenceResponse)
async def predict(
    model_id: UUID,
    payload: InferenceRequest,
    request: Request,
    uow: UnitOfWorkDep,
    store: ArtifactStoreDep,
    runtime_cache: ModelRuntimeCacheDep,
) -> InferenceResponse:
    settings = request.app.state.settings
    request_id = getattr(request.state, "request_id", None)
    result = await RunInference(
        uow,
        store,
        runtime_cache,
        trusted_checksums=settings.trusted_artifact_checksums,
        max_batch_size=settings.INFERENCE_MAX_BATCH_SIZE,
        load_timeout_seconds=settings.MODEL_LOAD_TIMEOUT_SECONDS,
        inference_timeout_seconds=settings.INFERENCE_TIMEOUT_SECONDS,
        auto_trust_artifacts=settings.ARTIFACT_TRUST_POLICY == "auto",
        tracer=getattr(request.app.state, "tracer", None),
    ).execute(
        model_id,
        payload.features,
        request_id=request_id,
    )
    return InferenceResponse.from_result(result)
