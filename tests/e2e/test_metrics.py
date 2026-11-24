import asyncio
import io
import logging
from collections.abc import Iterator
from typing import Any, cast

import joblib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from atlas_ml_platform.config import Settings
from atlas_ml_platform.core.application import create_app

ARTIFACTS_URL = "/api/v1/artifacts"
MODELS_URL = "/api/v1/models"
HEALTH_URL = "/api/v1/health"
MIDDLEWARE_LOGGER = "atlas_ml_platform.core.middleware"

IRIS_ROWS = [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 4.4, 1.4]]
WRONG_WIDTH_ROWS = [[987654.125, 123456.25, 456789.5]]
WRONG_WIDTH_VALUES = ("987654.125", "123456.25", "456789.5")

HTTP_REQUESTS = "atlas_http_requests_total"
HTTP_DURATION = "atlas_http_request_duration_seconds"
INFERENCE_REQUESTS = "atlas_inference_requests_total"
INFERENCE_DURATION = "atlas_inference_duration_seconds"
MODEL_LOADS = "atlas_model_load_total"
MODEL_LOAD_DURATION = "atlas_model_load_duration_seconds"
ARTIFACT_READS = "atlas_artifact_read_total"
ARTIFACT_READ_DURATION = "atlas_artifact_read_duration_seconds"
DB_POOL = "atlas_db_pool_connections"

EXPECTED_FAMILIES = frozenset(
    {
        HTTP_REQUESTS,
        HTTP_DURATION,
        INFERENCE_REQUESTS,
        INFERENCE_DURATION,
        MODEL_LOADS,
        MODEL_LOAD_DURATION,
        ARTIFACT_READS,
        ARTIFACT_READ_DURATION,
        DB_POOL,
    }
)

LabelKey = tuple[tuple[str, str], ...]
SampleKey = tuple[str, LabelKey]


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


@pytest.fixture
def metrics_client(test_settings: Settings) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        DEBUG=False,
        DATABASE_URL=test_settings.DATABASE_URL,
        S3_BUCKET="atlas-models-test",
        ARTIFACT_TRUST_POLICY="auto",
    )
    with TestClient(create_app(settings=settings)) as client:
        yield client


@pytest.fixture
def deployed_iris(
    metrics_client: TestClient,
    iris_artifact_bytes: bytes,
) -> Iterator[tuple[TestClient, dict[str, Any], dict[str, Any]]]:
    artifact, model, version = _deploy_iris(metrics_client, iris_artifact_bytes)
    try:
        yield metrics_client, model, version
    finally:
        _delete_artifact(metrics_client, artifact)


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
            "name": f"metrics-iris-{artifact['id'][:8]}",
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
):
    return client.post(
        f"{MODELS_URL}/{model_id}/predictions",
        json={"features": features},
    )


def _label_key(labels: dict[str, str]) -> LabelKey:
    return tuple(sorted(labels.items()))


def _scrape(client: TestClient) -> tuple[str, dict[SampleKey, float]]:
    response = client.get("/metrics")
    assert response.status_code == 200, response.text
    text = response.text
    samples: dict[SampleKey, float] = {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            samples[(sample.name, _label_key(sample.labels))] = sample.value
    return text, samples


def _value(samples: dict[SampleKey, float], name: str, **labels: str) -> float:
    return samples.get((name, _label_key(labels)), 0.0)


def _delta(
    before: dict[SampleKey, float],
    after: dict[SampleKey, float],
    name: str,
    **labels: str,
) -> float:
    return _value(after, name, **labels) - _value(before, name, **labels)


def test_metrics_endpoint_serves_prometheus_text_with_expected_families(
    deployed_iris: tuple[TestClient, dict[str, Any], dict[str, Any]],
) -> None:
    client, model, _ = deployed_iris
    assert _predict(client, model["id"], IRIS_ROWS).status_code == 200

    response = client.get("/metrics")

    assert response.status_code == 200
    content_type = response.headers["content-type"]
    assert content_type.startswith("text/plain")
    assert "version=" in content_type
    families = tuple(text_string_to_metric_families(response.text))
    names = {family.name for family in families} | {
        sample.name for family in families for sample in family.samples
    }
    assert EXPECTED_FAMILIES <= names

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/metrics" not in openapi.json()["paths"]


def test_http_metrics_label_requests_by_operation_and_status(
    metrics_client: TestClient,
) -> None:
    _, before = _scrape(metrics_client)

    assert metrics_client.get(HEALTH_URL).status_code == 200
    assert metrics_client.get("/api/v1/not-a-real-route").status_code == 404

    _, after = _scrape(metrics_client)

    assert (
        _delta(
            before,
            after,
            HTTP_REQUESTS,
            method="GET",
            route="health_check",
            status_code="200",
        )
        == 1
    )
    assert (
        _delta(
            before,
            after,
            HTTP_REQUESTS,
            method="GET",
            route="unmatched",
            status_code="404",
        )
        == 1
    )
    assert (
        _delta(
            before,
            after,
            f"{HTTP_DURATION}_count",
            method="GET",
            route="health_check",
        )
        == 1
    )

    routes = {
        dict(labels)["route"]
        for name, labels in after
        if name in {HTTP_REQUESTS, f"{HTTP_DURATION}_count"}
    }
    assert routes
    assert all(not route.startswith("/") for route in routes)
    assert "metrics_endpoint" not in routes


def test_inference_metrics_track_cold_load_then_cache_hit(
    deployed_iris: tuple[TestClient, dict[str, Any], dict[str, Any]],
) -> None:
    client, model, _ = deployed_iris
    _, before = _scrape(client)

    assert _predict(client, model["id"], IRIS_ROWS).status_code == 200
    _, after_cold = _scrape(client)

    assert (
        _delta(
            before,
            after_cold,
            INFERENCE_REQUESTS,
            outcome="success",
            cache_hit="false",
        )
        == 1
    )
    assert (
        _delta(
            before,
            after_cold,
            INFERENCE_REQUESTS,
            outcome="success",
            cache_hit="true",
        )
        == 0
    )
    assert _delta(before, after_cold, MODEL_LOADS, outcome="success") == 1
    assert _delta(before, after_cold, ARTIFACT_READS, outcome="success") == 1

    assert _predict(client, model["id"], IRIS_ROWS).status_code == 200
    _, after_warm = _scrape(client)

    assert (
        _delta(
            after_cold,
            after_warm,
            INFERENCE_REQUESTS,
            outcome="success",
            cache_hit="true",
        )
        == 1
    )
    assert (
        _delta(
            after_cold,
            after_warm,
            INFERENCE_REQUESTS,
            outcome="success",
            cache_hit="false",
        )
        == 0
    )
    assert _delta(after_cold, after_warm, MODEL_LOADS, outcome="success") == 0
    assert _delta(after_cold, after_warm, ARTIFACT_READS, outcome="success") == 0


def test_invalid_feature_count_records_invalid_input_without_identity_labels(
    deployed_iris: tuple[TestClient, dict[str, Any], dict[str, Any]],
) -> None:
    client, model, version = deployed_iris
    assert _predict(client, model["id"], IRIS_ROWS).status_code == 200

    _, before = _scrape(client)

    response = _predict(client, model["id"], WRONG_WIDTH_ROWS)

    assert response.status_code == 422, response.text
    assert response.json()["error_code"] == "invalid_inference_input"

    text, after = _scrape(client)
    assert (
        _delta(
            before,
            after,
            INFERENCE_REQUESTS,
            outcome="invalid_input",
            cache_hit="true",
        )
        == 1
    )
    assert (
        _delta(
            before,
            after,
            INFERENCE_REQUESTS,
            outcome="success",
            cache_hit="true",
        )
        == 0
    )

    label_values = {value for _, labels in after for _, value in labels}
    for high_cardinality in (model["id"], version["id"], *WRONG_WIDTH_VALUES):
        assert high_cardinality not in label_values
        assert high_cardinality not in text


def test_metrics_scrape_is_not_counted_or_access_logged(
    metrics_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=MIDDLEWARE_LOGGER):
        assert metrics_client.get(HEALTH_URL).status_code == 200
        assert [
            record.getMessage()
            for record in caplog.records
            if record.name == MIDDLEWARE_LOGGER
        ] == ["request_completed"]
        caplog.clear()

        _, before = _scrape(metrics_client)
        text, after = _scrape(metrics_client)

        assert [
            record for record in caplog.records if record.name == MIDDLEWARE_LOGGER
        ] == []

    http_before = {
        key: value for key, value in before.items() if key[0].startswith("atlas_http_")
    }
    http_after = {
        key: value for key, value in after.items() if key[0].startswith("atlas_http_")
    }
    assert http_after == http_before
    assert "metrics_endpoint" not in text
    assert 'route="/metrics"' not in text


def test_db_pool_gauge_reports_each_pool_state(metrics_client: TestClient) -> None:
    _, samples = _scrape(metrics_client)

    states = {
        dict(labels)["state"]: value
        for (name, labels), value in samples.items()
        if name == DB_POOL
    }
    assert set(states) == {"size", "checked_in", "checked_out"}
    assert all(value >= 0.0 for value in states.values())
