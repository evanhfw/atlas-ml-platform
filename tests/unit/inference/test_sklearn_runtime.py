import io
from collections.abc import Sequence

import joblib
import pytest
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from atlas_ml_platform.modules.inference.domain.errors import (
    InvalidInferenceInput,
    ModelLoadError,
    PredictionError,
)
from atlas_ml_platform.modules.inference.infrastructure.sklearn_runtime import (
    SklearnModelRuntime,
    SklearnModelRuntimeLoader,
)

IRIS_ROWS = [
    [5.1, 3.5, 1.4, 0.2],
    [6.7, 3.1, 4.4, 1.4],
    [6.3, 3.3, 6.0, 2.5],
]
IRIS_LABELS = [0, 1, 2]


@pytest.fixture(scope="module")
def iris_joblib_bytes() -> bytes:
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


def test_loads_joblib_bytes_and_predicts_known_iris_rows(
    iris_joblib_bytes: bytes,
) -> None:
    runtime = SklearnModelRuntimeLoader().load(iris_joblib_bytes)

    assert runtime.predict(IRIS_ROWS) == IRIS_LABELS


def test_rejects_rows_with_wrong_feature_count(iris_joblib_bytes: bytes) -> None:
    runtime = SklearnModelRuntimeLoader().load(iris_joblib_bytes)

    with pytest.raises(InvalidInferenceInput):
        _ = runtime.predict([[5.1, 3.5, 1.4]])


def test_rejects_input_without_rows(iris_joblib_bytes: bytes) -> None:
    runtime = SklearnModelRuntimeLoader().load(iris_joblib_bytes)

    with pytest.raises(InvalidInferenceInput):
        _ = runtime.predict([])


def test_rejects_corrupt_joblib_bytes() -> None:
    with pytest.raises(ModelLoadError):
        _ = SklearnModelRuntimeLoader().load(b"not-a-joblib-artifact")


def test_rejects_deserialized_object_without_predict_method() -> None:
    buffer = io.BytesIO()
    joblib.dump({"weights": [1, 2, 3]}, buffer)

    with pytest.raises(ModelLoadError, match="predict"):
        _ = SklearnModelRuntimeLoader().load(buffer.getvalue())


class _StubModel:
    n_features_in_ = 1

    def __init__(self, output: object) -> None:
        self._output = output

    def predict(self, features: Sequence[Sequence[float]]) -> object:
        return self._output


@pytest.mark.parametrize(
    "output",
    [
        [float("nan")],
        [float("inf")],
        [[1.0, 2.0]],
    ],
    ids=["nan", "infinity", "non-scalar"],
)
def test_rejects_predictions_that_are_not_finite_scalars(output: object) -> None:
    runtime = SklearnModelRuntime(_StubModel(output))

    with pytest.raises(PredictionError):
        _ = runtime.predict([[1.0]])


def test_wraps_model_prediction_failure() -> None:
    class _FailingModel:
        n_features_in_ = 1

        def predict(self, features: Sequence[Sequence[float]]) -> object:
            raise ValueError("estimator exploded")

    runtime = SklearnModelRuntime(_FailingModel())

    with pytest.raises(PredictionError, match="Model prediction failed"):
        _ = runtime.predict([[1.0]])
