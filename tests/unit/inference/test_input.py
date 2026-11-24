import pytest

from atlas_ml_platform.modules.inference.domain.errors import InvalidInferenceInput
from atlas_ml_platform.modules.inference.domain.input import InferenceInput

MAX_BATCH = 3
OVER_LIMIT = [[0.0]] * (MAX_BATCH + 1)


def test_accepts_rectangular_matrix_and_coerces_values_to_floats() -> None:
    parsed = InferenceInput.create([[1, 2.5], [3, 4]], max_batch_size=MAX_BATCH)

    assert parsed.features == ((1.0, 2.5), (3.0, 4.0))


def test_accepts_batch_exactly_at_limit() -> None:
    parsed = InferenceInput.create([[0.0]] * MAX_BATCH, max_batch_size=MAX_BATCH)

    assert len(parsed.features) == MAX_BATCH


@pytest.mark.parametrize(
    "features",
    [
        [],
        OVER_LIMIT,
        [[]],
        [[1.0, 2.0], [3.0]],
        [[float("nan")]],
        [[float("inf")]],
        [[float("-inf")]],
        [["not-a-number"]],
    ],
    ids=[
        "empty-batch",
        "over-batch-limit",
        "empty-row",
        "ragged",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "non-numeric",
    ],
)
def test_rejects_invalid_matrices(features) -> None:
    with pytest.raises(InvalidInferenceInput):
        _ = InferenceInput.create(features, max_batch_size=MAX_BATCH)
