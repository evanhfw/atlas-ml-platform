from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_ml_platform.infrastructure.database.session import get_db_session
from atlas_ml_platform.modules.model_registry.presentation.routes import (
    router as models_router,
)

api_router = APIRouter()

api_router.include_router(models_router)

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "atlas-ml-platform"}


@api_router.get("/health/database")
async def database_health(session: SessionDep):
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return {"status": "ok", "database": "reachable"}
