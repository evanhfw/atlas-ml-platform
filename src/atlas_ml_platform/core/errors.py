import re
from collections.abc import Awaitable, Callable, Mapping
from typing import cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from atlas_ml_platform.modules.artifacts.application.errors import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactTooLarge,
    ArtifactUriNotFound,
    UnsupportedArtifactType,
)
from atlas_ml_platform.modules.artifacts.domain.errors import InvalidArtifact
from atlas_ml_platform.modules.inference.domain.errors import (
    InferenceTimeout,
    InvalidInferenceInput,
    ModelLoadError,
    ModelLoadTimeout,
    PredictionError,
    UntrustedArtifact,
)
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
    ArtifactNotFound: 404,
    ArtifactUriNotFound: 404,
    ArtifactTooLarge: 413,
    UnsupportedArtifactType: 415,
    ArtifactIntegrityError: 500,
    InvalidArtifact: 422,
    InvalidInferenceInput: 422,
    UntrustedArtifact: 500,
    ModelLoadError: 500,
    ModelLoadTimeout: 504,
    PredictionError: 500,
    InferenceTimeout: 504,
}


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(Exception, _unhandled_handler)

    for error_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(error_type, _make_handler(status_code))


def _request_id(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    return str(request_id) if request_id is not None else None


def _headers(
    request: Request,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    headers = dict(extra or {})
    request_id = _request_id(request)
    if request_id is not None:
        headers["X-Request-ID"] = request_id
    return headers


def _error_code(exc: Exception) -> str:
    name = type(exc).__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _error_content(
    request: Request,
    *,
    detail: object,
    error_code: str,
) -> dict[str, object]:
    content: dict[str, object] = {
        "detail": detail,
        "error_code": error_code,
    }
    request_id = _request_id(request)
    if request_id is not None:
        content["request_id"] = request_id
    return content


def _make_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        error_code = _error_code(exc)
        request.state.error_code = error_code
        request.state.error_type = type(exc).__name__
        return JSONResponse(
            status_code=status_code,
            content=_error_content(
                request,
                detail=str(exc),
                error_code=error_code,
            ),
            headers=_headers(request),
        )

    return handler


async def _validation_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    validation = cast(RequestValidationError, exc)
    request.state.error_code = "request_validation_error"
    request.state.error_type = type(exc).__name__
    return JSONResponse(
        status_code=422,
        content=_error_content(
            request,
            detail=jsonable_encoder(validation.errors()),
            error_code="request_validation_error",
        ),
        headers=_headers(request),
    )


async def _http_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    request.state.error_code = "http_error"
    request.state.error_type = type(exc).__name__
    return JSONResponse(
        status_code=http_exc.status_code,
        content=_error_content(
            request,
            detail=jsonable_encoder(http_exc.detail),
            error_code="http_error",
        ),
        headers=_headers(request, http_exc.headers),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    request.state.error_code = "internal_error"
    request.state.error_type = type(exc).__name__
    return JSONResponse(
        status_code=500,
        content=_error_content(
            request,
            detail="Internal server error",
            error_code="internal_error",
        ),
        headers=_headers(request),
    )
