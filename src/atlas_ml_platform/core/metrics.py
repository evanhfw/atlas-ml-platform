from collections.abc import Iterable
from typing import Any, cast

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from sqlalchemy.pool import Pool

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"})

HTTP_REQUESTS = Counter(
    "atlas_http_requests_total",
    "HTTP requests by method, route template, and status code.",
    ["method", "route", "status_code"],
)
HTTP_REQUEST_DURATION = Histogram(
    "atlas_http_request_duration_seconds",
    "HTTP request duration by method and route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
INFERENCE_REQUESTS = Counter(
    "atlas_inference_requests_total",
    "Inference requests by outcome and cache hit.",
    ["outcome", "cache_hit"],
)
INFERENCE_DURATION = Histogram(
    "atlas_inference_duration_seconds",
    "End-to-end inference duration by outcome and cache hit.",
    ["outcome", "cache_hit"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
MODEL_LOADS = Counter(
    "atlas_model_load_total",
    "Model artifact load attempts by outcome.",
    ["outcome"],
)
MODEL_LOAD_DURATION = Histogram(
    "atlas_model_load_duration_seconds",
    "Model artifact load duration by outcome.",
    ["outcome"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
ARTIFACT_READS = Counter(
    "atlas_artifact_read_total",
    "Artifact reads by outcome.",
    ["outcome"],
)
ARTIFACT_READ_DURATION = Histogram(
    "atlas_artifact_read_duration_seconds",
    "Artifact read duration by outcome.",
    ["outcome"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)


def observe_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    method_label = method.upper() if method.upper() in _HTTP_METHODS else "OTHER"
    status_label = str(status_code)
    HTTP_REQUESTS.labels(
        method=method_label,
        route=route,
        status_code=status_label,
    ).inc()
    HTTP_REQUEST_DURATION.labels(method=method_label, route=route).observe(
        max(duration_seconds, 0.0)
    )


def observe_inference(
    *,
    outcome: str,
    cache_hit: bool,
    duration_seconds: float,
) -> None:
    cache_label = "true" if cache_hit else "false"
    INFERENCE_REQUESTS.labels(outcome=outcome, cache_hit=cache_label).inc()
    INFERENCE_DURATION.labels(outcome=outcome, cache_hit=cache_label).observe(
        max(duration_seconds, 0.0)
    )


def observe_model_load(*, outcome: str, duration_seconds: float) -> None:
    MODEL_LOADS.labels(outcome=outcome).inc()
    MODEL_LOAD_DURATION.labels(outcome=outcome).observe(max(duration_seconds, 0.0))


def observe_artifact_read(*, outcome: str, duration_seconds: float) -> None:
    ARTIFACT_READS.labels(outcome=outcome).inc()
    ARTIFACT_READ_DURATION.labels(outcome=outcome).observe(max(duration_seconds, 0.0))


def metrics_endpoint(_request: Request) -> Response:
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


class DatabasePoolCollector:
    """Collect pool gauges lazily when Prometheus scrapes /metrics."""

    def __init__(self, pool: Pool) -> None:
        self._pool: Pool = pool

    def collect(self) -> Iterable[Metric]:
        gauge = GaugeMetricFamily(
            "atlas_db_pool_connections",
            "SQLAlchemy pool connections by state.",
            labels=["state"],
        )
        try:
            pool = cast(Any, self._pool)
            gauge.add_metric(["size"], float(pool.size()))
            gauge.add_metric(["checked_in"], float(pool.checkedin()))
            gauge.add_metric(["checked_out"], float(pool.checkedout()))
        except Exception:  # noqa: BLE001 - a scrape must never fail the app
            return
        yield gauge
