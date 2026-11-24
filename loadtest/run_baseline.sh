#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
USERS="${USERS:-20}"
SPAWN_RATE="${SPAWN_RATE:-5}"
DURATION="${DURATION:-60s}"
RESULTS_DIR="${RESULTS_DIR:-loadtest/results}"
STATE_FILE="loadtest/state.json"

mkdir -p "$RESULTS_DIR"

curl -fsS "$BASE_URL/api/v1/health/ready" >/dev/null

uv run python loadtest/prepare.py --base-url "$BASE_URL" --output "$STATE_FILE"

MODEL_ID="$(jq -r .model_id "$STATE_FILE")"
ARTIFACT_ID="$(jq -r .artifact_id "$STATE_FILE")"
APP_PID="$(pgrep -af 'python.*uvicorn atlas_ml_platform.main:app' | awk '{print $1}' | head -1)"

if [[ -z "$APP_PID" ]]; then
  echo "Could not find the uvicorn process; start the app before running the baseline." >&2
  exit 1
fi

uv run python loadtest/observe.py \
  --pid "$APP_PID" \
  --duration "${OBSERVE_SECONDS:-75}" \
  --output "$RESULTS_DIR/app-resources.csv" &
OBSERVER_PID=$!

MODEL_ID="$MODEL_ID" ARTIFACT_ID="$ARTIFACT_ID" \
  uv run locust -f loadtest/locustfile.py \
    --headless \
    -u "$USERS" \
    -r "$SPAWN_RATE" \
    -t "$DURATION" \
    --host "$BASE_URL" \
    --csv "$RESULTS_DIR/baseline" \
    --csv-full-history \
    --loglevel WARNING

wait "$OBSERVER_PID"

echo "Locust CSV: $RESULTS_DIR/baseline_stats.csv"
echo "Resource CSV: $RESULTS_DIR/app-resources.csv"
cat "$STATE_FILE"
