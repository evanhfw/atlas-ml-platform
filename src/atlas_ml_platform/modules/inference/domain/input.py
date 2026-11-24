import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from atlas_ml_platform.modules.inference.domain.errors import InvalidInferenceInput


@dataclass(frozen=True, slots=True)
class InferenceInput:
    """A validated, rectangular feature matrix."""

    features: tuple[tuple[float, ...], ...]

    @classmethod
    def create(
        cls,
        features: Sequence[Sequence[float]],
        *,
        max_batch_size: int,
    ) -> Self:
        if not features:
            raise InvalidInferenceInput("At least one feature row is required")
        if len(features) > max_batch_size:
            raise InvalidInferenceInput(
                f"Batch size exceeds the maximum of {max_batch_size}"
            )

        width = len(features[0])
        if width == 0:
            raise InvalidInferenceInput("Feature rows must not be empty")

        rows: list[tuple[float, ...]] = []
        for row in features:
            if len(row) != width:
                raise InvalidInferenceInput("All feature rows must have equal length")
            try:
                values = tuple(float(value) for value in row)
            except (TypeError, ValueError) as exc:
                raise InvalidInferenceInput("Feature values must be numeric") from exc
            if any(not math.isfinite(value) for value in values):
                raise InvalidInferenceInput("Feature values must be finite")
            rows.append(values)

        return cls(tuple(rows))
