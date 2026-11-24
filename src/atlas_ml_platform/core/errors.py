from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from atlas_ml_platform.modules.model_registry.application.errors import (
    InvalidPagination,
    ModelNameAlreadyExists,
    ModelNotFound,
)
from atlas_ml_platform.modules.model_registry.domain import InvalidModelName


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ModelNotFound)
    async def _handle_model_not_found(
        _request: Request,
        exc: ModelNotFound,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ModelNameAlreadyExists)
    async def _handle_model_name_conflict(
        _request: Request,
        exc: ModelNameAlreadyExists,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidModelName)
    async def _handle_invalid_model_name(
        _request: Request,
        exc: InvalidModelName,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidPagination)
    async def _handle_invalid_pagination(
        _request: Request,
        exc: InvalidPagination,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
