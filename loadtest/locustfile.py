"""Locust workload for the Atlas ML Platform baseline.

Required environment:
    MODEL_ID       active benchmark model ID
    ARTIFACT_ID    optional artifact metadata ID
    BASE_URL       default http://127.0.0.1:8000

Run headless:
    uv run locust -f loadtest/locustfile.py --headless \
      -u 20 -r 5 -t 60s --host "$BASE_URL" \
      --csv loadtest/results/baseline --csv-full-history
"""

import os

from locust import HttpUser, between, task

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
MODEL_ID = os.getenv("MODEL_ID", "")
ARTIFACT_ID = os.getenv("ARTIFACT_ID", "")

FEATURES = [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 4.4, 1.4]]


class AtlasUser(HttpUser):
    host = BASE_URL
    wait_time = between(0.05, 0.2)

    def on_start(self) -> None:
        if not MODEL_ID:
            raise RuntimeError("MODEL_ID is required for the benchmark workload")

    @task(1)
    def liveness(self) -> None:
        self.client.get("/api/v1/health", name="GET /api/v1/health")

    @task(3)
    def read_model(self) -> None:
        self.client.get(
            f"/api/v1/models/{MODEL_ID}",
            name="GET /api/v1/models/{model_id}",
        )

    @task(1)
    def read_artifact(self) -> None:
        if ARTIFACT_ID:
            self.client.get(
                f"/api/v1/artifacts/{ARTIFACT_ID}",
                name="GET /api/v1/artifacts/{artifact_id}",
            )

    @task(6)
    def predict(self) -> None:
        self.client.post(
            f"/api/v1/models/{MODEL_ID}/predictions",
            json={"features": FEATURES},
            name="POST /api/v1/models/{model_id}/predictions",
        )
