from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from atlas_ml_platform.modules.inference.application.ports import PredictionValue
from atlas_ml_platform.modules.inference.application.use_cases import InferenceResult


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: list[list[float]] = Field(min_length=1)


class InferenceResponse(BaseModel):
    request_id: UUID
    model_id: UUID
    model_version_id: UUID
    version_number: int
    predictions: list[PredictionValue]
    latency_ms: float

    @classmethod
    def from_result(cls, result: InferenceResult) -> Self:
        return cls(
            request_id=result.request_id,
            model_id=result.model_id,
            model_version_id=result.model_version_id,
            version_number=result.version_number,
            predictions=result.predictions,
            latency_ms=round(result.latency_ms, 2),
        )
