import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_ml_platform.api.dependencies import ArtifactStoreDep
from atlas_ml_platform.infrastructure.database.session import get_db_session
from atlas_ml_platform.modules.artifacts.presentation.routes import (
    router as artifacts_router,
)
from atlas_ml_platform.modules.inference.presentation.routes import (
    router as inference_router,
)
from atlas_ml_platform.modules.model_registry.presentation.routes import (
    router as models_router,
)

api_router = APIRouter()

api_router.include_router(models_router)
api_router.include_router(artifacts_router)
api_router.include_router(inference_router)

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "atlas-ml-platform"}


@api_router.get("/health/ready")
async def readiness_check(
    request: Request,
    session: SessionDep,
    store: ArtifactStoreDep,
):
    if getattr(request.app.state, "shutting_down", False):
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "shutting_down",
                "checks": {},
            },
        )
    if not getattr(request.app.state, "ready", False):
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "starting",
                "checks": {},
            },
        )

    timeout = request.app.state.settings.READINESS_TIMEOUT_SECONDS

    async def check_database() -> bool:
        try:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=timeout,
            )
        except (SQLAlchemyError, OSError, TimeoutError):
            return False
        return True

    async def check_artifact_store() -> bool:
        try:
            await asyncio.wait_for(store.healthcheck(), timeout=timeout)
        except Exception:  # noqa: BLE001 - readiness must report, not raise
            return False
        return True

    database_ok, store_ok = await asyncio.gather(
        check_database(),
        check_artifact_store(),
    )
    checks = {
        "database": "ok" if database_ok else "error",
        "artifact_store": "ok" if store_ok else "error",
    }

    if database_ok and store_ok:
        return {"status": "ready", "checks": checks}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "checks": checks},
    )
