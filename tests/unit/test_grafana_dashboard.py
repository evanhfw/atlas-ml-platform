import json
from pathlib import Path
from typing import Any

import pytest

DASHBOARD_PATH = (
    Path(__file__).resolve().parents[2]
    / "docker"
    / "grafana"
    / "dashboards"
    / "atlas-ml-platform.json"
)

PANEL_METRICS = {
    "HTTP request rate": "atlas_http_requests_total",
    "HTTP p95 latency": "atlas_http_request_duration_seconds_bucket",
    "Inference rate": "atlas_inference_requests_total",
    "Inference p95 latency": "atlas_inference_duration_seconds_bucket",
    "Model load outcomes": "atlas_model_load_total",
    "Database pool connections": "atlas_db_pool_connections",
    "HTTP errors": "atlas_http_requests_total",
}


def _panels() -> list[dict[str, Any]]:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    return dashboard["panels"]


def test_dashboard_defines_exactly_the_expected_panels() -> None:
    panels = _panels()

    assert len(panels) == 7
    assert {panel["title"] for panel in panels} == set(PANEL_METRICS)
    assert len({panel["id"] for panel in panels}) == len(panels)


@pytest.mark.parametrize("title,metric", PANEL_METRICS.items())
def test_dashboard_panel_queries_its_core_metric(title: str, metric: str) -> None:
    matching = [panel for panel in _panels() if panel["title"] == title]

    assert len(matching) == 1
    expressions = [target["expr"] for target in matching[0]["targets"]]
    assert any(metric in expression for expression in expressions)
