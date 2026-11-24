import json
import logging
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_ml_platform.core.errors import register_exception_handlers
from atlas_ml_platform.core.logging import JsonFormatter
from atlas_ml_platform.core.middleware import RequestContextMiddleware

MODELS_URL = "/api/v1/models"
MIDDLEWARE_LOGGER = "atlas_ml_platform.core.middleware"


def _app_records(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    return [record for record in records if record.name.startswith("atlas_ml_platform")]


class _JsonCaptureHandler(logging.Handler):
    """Capture records exactly as the production formatter emits them."""

    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[dict[str, Any]] = []
        self.setFormatter(JsonFormatter(service="atlas-test", environment="testing"))

    def emit(self, record: logging.LogRecord) -> None:
        self.payloads.append(json.loads(self.format(record)))


def test_successful_request_carries_generated_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert UUID(response.headers["x-request-id"])


def test_unknown_route_returns_http_error_with_correlation(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    request_id = response.headers["x-request-id"]
    assert UUID(request_id)
    body = response.json()
    assert body["error_code"] == "http_error"
    assert body["request_id"] == request_id


def test_missing_model_returns_domain_error_code_and_correlation(
    client: TestClient,
) -> None:
    missing = uuid4()

    response = client.get(f"{MODELS_URL}/{missing}")

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "model_not_found"
    assert str(missing) in body["detail"]
    assert body["request_id"] == response.headers["x-request-id"]


def test_request_validation_returns_validation_error_contract(
    client: TestClient,
) -> None:
    response = client.post(
        MODELS_URL,
        json={"name": "", "framework": "", "task_type": ""},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "request_validation_error"
    assert isinstance(body["detail"], list)
    assert body["detail"]
    assert body["request_id"] == response.headers["x-request-id"]


def test_valid_incoming_request_id_is_reused(client: TestClient) -> None:
    supplied = uuid4()

    response = client.get(
        f"{MODELS_URL}/{uuid4()}",
        headers={"X-Request-ID": str(supplied)},
    )

    assert response.headers["x-request-id"] == str(supplied)
    assert response.json()["request_id"] == str(supplied)


def test_invalid_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/api/v1/does-not-exist",
        headers={"X-Request-ID": "not-a-uuid"},
    )

    generated = response.headers["x-request-id"]
    assert generated != "not-a-uuid"
    assert UUID(generated)
    assert response.json()["request_id"] == generated


def test_successful_request_emits_exactly_one_access_log(
    client: TestClient,
    caplog,
) -> None:
    caplog.clear()
    capture = _JsonCaptureHandler()
    middleware_logger = logging.getLogger(MIDDLEWARE_LOGGER)
    middleware_logger.addHandler(capture)
    try:
        with caplog.at_level(logging.INFO):
            response = client.get("/api/v1/health")
    finally:
        middleware_logger.removeHandler(capture)

    records = _app_records(caplog.records)
    assert len(records) == 1
    assert len(capture.payloads) == 1
    record = cast(Any, records[0])
    assert record.name == MIDDLEWARE_LOGGER
    assert record.getMessage() == "request_completed"
    assert record.levelno == logging.INFO
    assert record.method == "GET"
    assert record.path == "/api/v1/health"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0.0
    assert capture.payloads[0]["request_id"] == response.headers["x-request-id"]


def test_domain_404_emits_exactly_one_warning(client: TestClient, caplog) -> None:
    caplog.clear()
    capture = _JsonCaptureHandler()
    middleware_logger = logging.getLogger(MIDDLEWARE_LOGGER)
    middleware_logger.addHandler(capture)
    try:
        with caplog.at_level(logging.INFO):
            response = client.get(f"{MODELS_URL}/{uuid4()}")
    finally:
        middleware_logger.removeHandler(capture)

    records = _app_records(caplog.records)
    assert len(records) == 1
    assert len(capture.payloads) == 1
    record = cast(Any, records[0])
    assert record.name == MIDDLEWARE_LOGGER
    assert record.getMessage() == "request_failed"
    assert record.levelno == logging.WARNING
    assert record.status_code == 404
    assert record.error_code == "model_not_found"
    assert record.error_type == "ModelNotFound"
    assert capture.payloads[0]["request_id"] == response.headers["x-request-id"]


def _app_with_unhandled_error() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("do-not-leak-detail")

    return app


def test_unhandled_exception_is_logged_once_and_detail_is_not_leaked(caplog) -> None:
    with TestClient(
        _app_with_unhandled_error(), raise_server_exceptions=False
    ) as client:
        caplog.clear()
        with caplog.at_level(logging.INFO):
            response = client.get("/boom")

    records = _app_records(caplog.records)
    assert len(records) == 1
    record = cast(Any, records[0])
    assert record.name == MIDDLEWARE_LOGGER
    assert record.getMessage() == "request_failed"
    assert record.levelno == logging.ERROR
    assert record.status_code == 500
    assert record.error_type == "RuntimeError"
    assert record.exc_info is not None
    stack = logging.Formatter().formatException(record.exc_info)
    assert "Traceback (most recent call last)" in stack
    assert "RuntimeError: do-not-leak-detail" in stack

    body = response.json()
    assert response.status_code == 500
    assert body["detail"] == "Internal server error"
    assert body["error_code"] == "internal_error"
    assert body["request_id"] == response.headers["x-request-id"]
    assert "do-not-leak-detail" not in response.text
    assert "RuntimeError" not in response.text
