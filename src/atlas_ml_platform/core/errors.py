from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from atlas_ml_platform.modules.model_registry.application.errors import (
    InvalidPagination,
    ModelNameAlreadyExists,
    ModelNotFound,
    NoActiveVersion,
    VersionNotFound,
    VersionNotReady,
    VersionNumberConflict,
)
from atlas_ml_platform.modules.model_registry.domain import (
    InvalidArtifactUri,
    InvalidModelName,
    InvalidVersionNumber,
    InvalidVersionTransition,
)

_ERROR_STATUS: dict[type[Exception], int] = {
    ModelNotFound: 404,
    VersionNotFound: 404,
    NoActiveVersion: 404,
    ModelNameAlreadyExists: 409,
    VersionNotReady: 409,
    VersionNumberConflict: 409,
    InvalidVersionTransition: 409,
    InvalidModelName: 422,
    InvalidPagination: 422,
    InvalidVersionNumber: 422,
    InvalidArtifactUri: 422,
}


def register_exception_handlers(app: FastAPI) -> None:
    for error_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(error_type, _make_handler(status_code))


def _make_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler
