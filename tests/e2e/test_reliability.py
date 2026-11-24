import asyncio
import time
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_ml_platform.core.application import create_app
from atlas_ml_platform.core.shutdown import RequestTracker

HEALTH_URL = "/api/v1/health"
READY_URL = "/api/v1/health/ready"
MODELS_URL = "/api/v1/models"
METRICS_URL = "/metrics"


class RecordingTracker(RequestTracker):
    """Count begin() calls so probe tracking can be observed, not inferred."""

    def __init__(self) -> None:
        super().__init__()
        self.begins: int = 0

    def begin(self) -> None:
        self.begins += 1
        super().begin()


def test_health_and_readiness_report_healthy_dependencies(client: TestClient) -> None:
    health = client.get(HEALTH_URL)
    assert health.status_code == 200

    ready = client.get(READY_URL)
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "checks": {"database": "ok", "artifact_store": "ok"},
    }

    app = cast(FastAPI, client.app)
    assert app.state.request_tracker.in_flight == 0


def test_probes_are_exempt_from_request_tracking_but_routes_are_not(
    client: TestClient,
) -> None:
    app = cast(FastAPI, client.app)
    tracker = RecordingTracker()
    app.state.request_tracker = tracker

    assert client.get(HEALTH_URL).status_code == 200
    assert client.get(READY_URL).status_code == 200
    assert client.get(METRICS_URL).status_code == 200

    assert tracker.begins == 0
    assert tracker.in_flight == 0

    assert client.get(MODELS_URL).status_code == 200

    assert tracker.begins == 1
    assert tracker.in_flight == 0


def test_shutdown_serves_probes_and_rejects_new_work(client: TestClient) -> None:
    app = cast(FastAPI, client.app)
    app.state.shutting_down = True
    try:
        health = client.get(HEALTH_URL)
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        ready = client.get(READY_URL)
        assert ready.status_code == 503
        assert ready.json() == {
            "status": "not_ready",
            "reason": "shutting_down",
            "checks": {},
        }

        assert client.get(METRICS_URL).status_code == 200

        rejected = client.get(MODELS_URL)
        assert rejected.status_code == 503
        payload = rejected.json()
        assert payload["error_code"] == "service_unavailable"
        assert payload["detail"] == "Service is shutting down"
        request_id = UUID(payload["request_id"])
        assert rejected.headers["X-Request-ID"] == str(request_id)
    finally:
        app.state.shutting_down = False


def test_readiness_reports_starting_before_ready_is_set(client: TestClient) -> None:
    app = cast(FastAPI, client.app)
    app.state.ready = False
    try:
        ready = client.get(READY_URL)
        assert ready.status_code == 503
        assert ready.json() == {
            "status": "not_ready",
            "reason": "starting",
            "checks": {},
        }
    finally:
        app.state.ready = True


def test_readiness_reports_artifact_store_failure_with_database_still_ok(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = cast(FastAPI, client.app)

    async def failing_healthcheck() -> None:
        raise RuntimeError("artifact store unreachable")

    monkeypatch.setattr(app.state.artifact_store, "healthcheck", failing_healthcheck)

    ready = client.get(READY_URL)

    assert ready.status_code == 503
    assert ready.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "artifact_store": "error"},
    }


def test_readiness_times_out_a_slow_artifact_store(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = cast(FastAPI, client.app)
    monkeypatch.setattr(app.state.settings, "READINESS_TIMEOUT_SECONDS", 0.05)

    async def slow_healthcheck() -> None:
        await asyncio.sleep(1.0)

    monkeypatch.setattr(app.state.artifact_store, "healthcheck", slow_healthcheck)

    ready = client.get(READY_URL)

    assert ready.status_code == 503
    assert ready.json()["checks"] == {
        "database": "ok",
        "artifact_store": "error",
    }


def test_shutdown_closes_the_artifact_store(test_settings, monkeypatch) -> None:
    app = create_app(settings=test_settings)
    closed: list[object] = []

    with TestClient(app):
        store = app.state.artifact_store

        async def record_close() -> None:
            closed.append(store)

        monkeypatch.setattr(store, "close", record_close)

    assert closed == [store]


def test_shutdown_waits_for_in_flight_requests_up_to_the_grace_period(
    test_settings,
) -> None:
    grace_seconds = 0.05
    settings = test_settings.model_copy(
        update={"SHUTDOWN_GRACE_SECONDS": grace_seconds}
    )
    app = create_app(settings=settings)

    with TestClient(app):
        app.state.request_tracker.begin()
        started = time.perf_counter()

    elapsed = time.perf_counter() - started

    assert elapsed >= grace_seconds
