import asyncio
import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import joblib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app
from atlas_ml_platform.core.logging import JsonFormatter

ARTIFACTS_URL = "/api/v1/artifacts"
MODELS_URL = "/api/v1/models"
PREDICTIONS_ROUTE = "/api/v1/models/{model_id}/predictions"
SERVER_SPAN_NAME = f"POST {PREDICTIONS_ROUTE}"
INFERENCE_LOGGER = "atlas_ml_platform.modules.inference.application.use_cases"
MIDDLEWARE_LOGGER = "atlas_ml_platform.core.middleware"

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_SPAN_ID = "00f067aa0ba902b7"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"

IRIS_ROWS = [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 4.4, 1.4]]
IRIS_LABELS = [0, 1]
DISTINCTIVE_FEATURES = [[987654.125, 123456.25, 456789.5, 789123.75]]
FEATURE_FRAGMENTS = ("987654.125", "123456.25", "456789.5", "789123.75")


@pytest.fixture(scope="session")
def iris_artifact_bytes() -> bytes:
    features, labels = load_iris(return_X_y=True)
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=0)),
        ]
    )
    model.fit(features, labels)

    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    return buffer.getvalue()


class _JsonCaptureHandler(logging.Handler):
    """Format records at emit time so the active span is captured."""

    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.setFormatter(JsonFormatter(service="atlas-test", environment="testing"))

    def emit(self, record: logging.LogRecord) -> None:
        emitted = self.format(record)
        self.emitted.append(emitted)
        self.payloads.append(json.loads(emitted))


def _settings(test_settings: Settings) -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        APP_ENV="testing",
        DEBUG=False,
        DATABASE_URL=test_settings.DATABASE_URL,
        S3_BUCKET="atlas-models-test",
        ARTIFACT_TRUST_POLICY="auto",
        OTEL_ENABLED=True,
        OTEL_SERVICE_NAME="atlas-tracing-e2e",
        OTEL_SERVICE_VERSION="1.2.3",
    )


@contextmanager
def _traced_client(
    test_settings: Settings,
) -> Iterator[tuple[TestClient, InMemorySpanExporter]]:
    exporter = InMemorySpanExporter()
    app = create_app(settings=_settings(test_settings), span_exporter=exporter)
    with TestClient(app) as client:
        yield client, exporter


def _deploy_iris(
    client: TestClient,
    artifact_bytes: bytes,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    uploaded = client.post(
        ARTIFACTS_URL,
        files={"file": ("model.joblib", artifact_bytes, "application/x-joblib")},
    )
    assert uploaded.status_code == 201, uploaded.text
    artifact = uploaded.json()

    created = client.post(
        MODELS_URL,
        json={
            "name": f"trace-iris-{artifact['id'][:8]}",
            "description": "Iris classifier",
            "framework": "sklearn",
            "task_type": "classification",
        },
    )
    assert created.status_code == 201, created.text
    model = created.json()

    version_response = client.post(
        f"{MODELS_URL}/{model['id']}/versions",
        json={"artifact_uri": artifact["uri"]},
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()

    base = f"{MODELS_URL}/{model['id']}/versions/{version['id']}"
    assert client.post(f"{base}/ready").status_code == 200
    assert client.post(f"{base}/activate").status_code == 200
    return artifact, model, version


def _delete_artifact(client: TestClient, artifact: dict[str, Any]) -> None:
    store = cast(FastAPI, client.app).state.artifact_store
    asyncio.run(store.delete(f"artifacts/{artifact['id']}"))


def _predict(
    client: TestClient,
    model_id: str,
    features: list[list[float]],
    *,
    traceparent: str = TRACEPARENT,
):
    return client.post(
        f"{MODELS_URL}/{model_id}/predictions",
        content=json.dumps({"features": features}),
        headers={"content-type": "application/json", "traceparent": traceparent},
    )


def _span_by_name(spans: tuple[ReadableSpan, ...], name: str) -> ReadableSpan:
    matched = [span for span in spans if span.name == name]
    assert len(matched) == 1, [(span.name, span.context) for span in spans]
    return matched[0]


def _parent_span_id(span: ReadableSpan) -> int:
    parent = span.parent
    assert parent is not None
    return parent.span_id


def _span_text(span: ReadableSpan) -> str:
    return json.dumps(
        {key: str(value) for key, value in (span.attributes or {}).items()}
    )


def test_traced_prediction_exports_server_and_inference_span_hierarchy(
    test_settings: Settings,
    iris_artifact_bytes: bytes,
) -> None:
    with _traced_client(test_settings) as (client, exporter):
        artifact, model, version = _deploy_iris(client, iris_artifact_bytes)
        try:
            response = _predict(client, model["id"], DISTINCTIVE_FEATURES)
            assert response.status_code == 200, response.text
        finally:
            _delete_artifact(client, artifact)

    spans = exporter.get_finished_spans()
    requested_trace_id = int(TRACE_ID, 16)
    server = _span_by_name(spans, SERVER_SPAN_NAME)

    server_context = server.context
    assert server_context is not None
    assert server_context.trace_id == requested_trace_id
    assert _parent_span_id(server) == int(PARENT_SPAN_ID, 16)
    assert server.attributes is not None
    assert server.attributes["http.route"] == PREDICTIONS_ROUTE

    assert [
        span.name
        for span in spans
        if span.name.endswith(" receive") or span.name.endswith(" send")
    ] == []

    inference_run = _span_by_name(spans, "inference.run")
    inference_context = inference_run.context
    assert inference_context is not None
    assert _parent_span_id(inference_run) == server_context.span_id
    for child_name in ("model.lookup", "artifact.fetch", "model.load", "model.predict"):
        child = _span_by_name(spans, child_name)
        assert _parent_span_id(child) == inference_context.span_id

    run_attributes = cast(dict[str, object], inference_run.attributes)
    assert run_attributes["model.id"] == model["id"]
    assert run_attributes["model.version_id"] == version["id"]
    assert run_attributes["model.version_number"] == 1
    assert run_attributes["inference.batch_size"] == 1
    assert run_attributes["inference.cache_hit"] is False
    assert run_attributes["inference.predictions_count"] == 1
    assert run_attributes["inference.outcome"] == "success"

    select_spans = [
        span
        for span in spans
        if span.name.split()[0] == "SELECT"
        and span.context is not None
        and span.context.trace_id == requested_trace_id
    ]
    assert select_spans, [span.name for span in spans]
    assert {span.context.trace_id for span in select_spans if span.context} == {
        requested_trace_id
    }
    lookup = _span_by_name(spans, "model.lookup")
    lookup_context = lookup.context
    assert lookup_context is not None
    assert any(
        span.parent is not None and span.parent.span_id == lookup_context.span_id
        for span in select_spans
    )

    resource = server.resource.attributes
    assert resource["service.name"] == "atlas-tracing-e2e"
    assert resource["service.version"] == "1.2.3"
    assert resource["deployment.environment"] == "testing"

    for span in spans:
        emitted = _span_text(span)
        for fragment in FEATURE_FRAGMENTS:
            assert fragment not in emitted, (span.name, emitted)


def test_inference_and_access_logs_share_requested_trace_without_features(
    test_settings: Settings,
    iris_artifact_bytes: bytes,
) -> None:
    capture = _JsonCaptureHandler()
    root = logging.getLogger()
    root.addHandler(capture)
    try:
        with _traced_client(test_settings) as (client, exporter):
            artifact, model, version = _deploy_iris(client, iris_artifact_bytes)
            try:
                response = _predict(client, model["id"], DISTINCTIVE_FEATURES)
                assert response.status_code == 200, response.text
            finally:
                _delete_artifact(client, artifact)
    finally:
        root.removeHandler(capture)

    spans = exporter.get_finished_spans()
    server = _span_by_name(spans, SERVER_SPAN_NAME)
    inference_run = _span_by_name(spans, "inference.run")
    server_context = server.context
    assert server_context is not None
    inference_context = inference_run.context
    assert inference_context is not None

    inference_logs = [
        payload
        for payload in capture.payloads
        if payload["logger"] == INFERENCE_LOGGER
        and payload["message"] == "inference_completed"
    ]
    assert len(inference_logs) == 1
    inference_log = inference_logs[0]
    assert inference_log["trace_id"] == TRACE_ID
    assert inference_log["span_id"] == format(inference_context.span_id, "016x")
    assert inference_log["model_id"] == model["id"]
    assert inference_log["version_id"] == version["id"]
    assert inference_log["rows"] == 1
    assert inference_log["outcome"] == "success"
    assert isinstance(inference_log["latency_ms"], float)
    assert inference_log["latency_ms"] >= 0.0

    access_logs = [
        payload
        for payload in capture.payloads
        if payload["logger"] == MIDDLEWARE_LOGGER
        and payload["message"] == "request_completed"
        and payload["path"] == f"{MODELS_URL}/{model['id']}/predictions"
    ]
    assert len(access_logs) == 1
    access_log = access_logs[0]
    assert access_log["trace_id"] == TRACE_ID
    assert access_log["span_id"] == format(server_context.span_id, "016x")

    for emitted in capture.emitted:
        for fragment in FEATURE_FRAGMENTS:
            assert fragment not in emitted, emitted


def test_cached_prediction_skips_artifact_fetch_and_model_load_spans(
    test_settings: Settings,
    iris_artifact_bytes: bytes,
) -> None:
    with _traced_client(test_settings) as (client, exporter):
        artifact, model, _ = _deploy_iris(client, iris_artifact_bytes)
        try:
            warm = _predict(client, model["id"], IRIS_ROWS)
            assert warm.status_code == 200, warm.text
            assert warm.json()["predictions"] == IRIS_LABELS

            exporter.clear()
            cached = _predict(client, model["id"], IRIS_ROWS)
            assert cached.status_code == 200, cached.text
            assert cached.json()["predictions"] == IRIS_LABELS
        finally:
            _delete_artifact(client, artifact)

    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert "artifact.fetch" not in names
    assert "model.load" not in names
    assert "model.predict" in names

    inference_run = _span_by_name(spans, "inference.run")
    assert (
        cast(dict[str, object], inference_run.attributes)["inference.cache_hit"] is True
    )
