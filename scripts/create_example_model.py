"""Train the deterministic example artifact used by the inference demo.

Run from the repository root:

    uv run python scripts/create_example_model.py

Then either keep local `ARTIFACT_TRUST_POLICY=auto`, or for production
allowlist mode add the printed checksum to `.env`:

    TRUSTED_ARTIFACT_CHECKSUMS=<checksum>

The allowlist is intentional: joblib/pickle deserialization can execute code,
so the runtime must never load an arbitrary uploaded artifact.
"""

import hashlib
from pathlib import Path

import joblib  # type: ignore[import-untyped]
from sklearn.datasets import load_iris  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import make_pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

OUTPUT_PATH = Path("example_model.joblib")


def main() -> None:
    features, target = load_iris(return_X_y=True)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=500, random_state=42),
    )
    model.fit(features, target)

    joblib.dump(model, OUTPUT_PATH)
    checksum = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()

    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")
    print(f"SHA-256: {checksum}")
    print("Local auto-trust mode needs no checksum entry.")
    print(f"For allowlist mode add to .env: TRUSTED_ARTIFACT_CHECKSUMS={checksum}")
    print("Example row: [5.1, 3.5, 1.4, 0.2]")


if __name__ == "__main__":
    main()
