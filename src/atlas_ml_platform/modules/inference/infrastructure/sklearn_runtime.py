import io
import math
from collections.abc import Sequence
from typing import Any, override

import joblib  # type: ignore[import-untyped]

from atlas_ml_platform.modules.inference.application.ports import (
    ModelRuntime,
    ModelRuntimeLoader,
    PredictionValue,
)
from atlas_ml_platform.modules.inference.domain.errors import (
    InvalidInferenceInput,
    ModelLoadError,
    PredictionError,
)


class SklearnModelRuntime(ModelRuntime):
    """Synchronous scikit-learn runtime; execute via a worker thread."""

    def __init__(self, model: Any) -> None:
        self._model: Any = model
        expected = getattr(model, "n_features_in_", None)
        self._expected_features: int | None = (
            int(expected) if expected is not None else None
        )

    @override
    def predict(self, features: Sequence[Sequence[float]]) -> list[PredictionValue]:
        if self._expected_features is not None and (
            not features or len(features[0]) != self._expected_features
        ):
            raise InvalidInferenceInput(
                f"Model expects {self._expected_features} features per row"
            )

        try:
            raw_predictions = self._model.predict(features)
        except InvalidInferenceInput:
            raise
        except Exception as exc:
            raise PredictionError("Model prediction failed") from exc

        return [_to_prediction_value(value) for value in raw_predictions]


class SklearnModelRuntimeLoader(ModelRuntimeLoader):
    """Deserialize trusted joblib artifacts into scikit-learn runtimes.

    The caller must enforce the trusted-checksum policy before invoking this
    loader. Unpickling a joblib artifact executes code embedded in the artifact.
    """

    @override
    def load(self, data: bytes) -> ModelRuntime:
        try:
            model = joblib.load(io.BytesIO(data))
        except Exception as exc:
            raise ModelLoadError("Failed to deserialize model artifact") from exc

        if not hasattr(model, "predict"):
            raise ModelLoadError("Artifact does not expose a predict method")
        return SklearnModelRuntime(model)


def _to_prediction_value(value: object) -> PredictionValue:
    item_method = getattr(value, "item", None)
    item = item_method() if callable(item_method) else value
    if isinstance(item, bool):
        return int(item)
    if isinstance(item, int):
        return item
    if isinstance(item, float):
        if not math.isfinite(item):
            raise PredictionError("Model returned a non-finite prediction")
        return item
    if isinstance(item, str):
        return item
    raise PredictionError("Model returned a non-scalar prediction")
