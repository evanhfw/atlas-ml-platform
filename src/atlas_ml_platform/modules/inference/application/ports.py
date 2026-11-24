from collections.abc import Sequence
from typing import Protocol

type PredictionValue = int | float | str


class ModelRuntime(Protocol):
    """Loaded model capable of synchronous prediction."""

    def predict(self, features: Sequence[Sequence[float]]) -> list[PredictionValue]:
        """Return one prediction per feature row."""
        ...


class ModelRuntimeLoader(Protocol):
    """Deserialize artifact bytes into a runtime."""

    def load(self, data: bytes) -> ModelRuntime: ...
