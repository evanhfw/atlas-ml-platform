"""Create a deterministic iris model, upload it, and activate a benchmark version.

The application must be running with `ARTIFACT_TRUST_POLICY=auto` (local dev)
or with the artifact checksum allowlisted. This script prints a JSON state file
and writes `loadtest/state.json` for the Locust run.
"""

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any

import httpx
import joblib  # type: ignore[import-untyped]
from sklearn.datasets import load_iris  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
STATE_PATH = Path("loadtest/state.json")


def _model_bytes() -> bytes:
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


def _post_json(
    client: httpx.Client,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=STATE_PATH)
    args = parser.parse_args()

    data = _model_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    name = f"benchmark-iris-{int(time.time())}"

    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        artifact = client.post(
            "/api/v1/artifacts",
            files={"file": ("benchmark-iris.joblib", data, "application/x-joblib")},
        )
        artifact.raise_for_status()
        artifact_body = artifact.json()

        model = _post_json(
            client,
            "/api/v1/models",
            {
                "name": name,
                "description": "M14 benchmark model",
                "framework": "sklearn",
                "task_type": "classification",
            },
        )
        version = _post_json(
            client,
            f"/api/v1/models/{model['id']}/versions",
            {"artifact_uri": artifact_body["uri"]},
        )
        client.post(
            f"/api/v1/models/{model['id']}/versions/{version['id']}/ready"
        ).raise_for_status()
        client.post(
            f"/api/v1/models/{model['id']}/versions/{version['id']}/activate"
        ).raise_for_status()

        features = [[5.1, 3.5, 1.4, 0.2], [6.7, 3.1, 4.4, 1.4]]
        cold_started = time.perf_counter()
        cold = client.post(
            f"/api/v1/models/{model['id']}/predictions",
            json={"features": features},
        )
        cold_ms = (time.perf_counter() - cold_started) * 1000
        cold.raise_for_status()

        warm_started = time.perf_counter()
        warm = client.post(
            f"/api/v1/models/{model['id']}/predictions",
            json={"features": features},
        )
        warm_ms = (time.perf_counter() - warm_started) * 1000
        warm.raise_for_status()

    state = {
        "base_url": args.base_url,
        "model_id": model["id"],
        "version_id": version["id"],
        "artifact_id": artifact_body["id"],
        "artifact_checksum": checksum,
        "artifact_bytes": len(data),
        "cold_inference_ms": round(cold_ms, 2),
        "warm_inference_ms": round(warm_ms, 2),
        "cold_predictions": cold.json()["predictions"],
        "warm_predictions": warm.json()["predictions"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
