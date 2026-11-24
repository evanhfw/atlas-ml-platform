import asyncio
import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import StatusCode, Tracer

from atlas_ml_platform.core.metrics import observe_inference
from atlas_ml_platform.modules.artifacts.application.content import (
    read_verified_artifact,
)
from atlas_ml_platform.modules.artifacts.application.errors import (
    ArtifactIntegrityError,
    ArtifactUriNotFound,
)
from atlas_ml_platform.modules.artifacts.application.ports import ArtifactStore
from atlas_ml_platform.modules.inference.application.ports import PredictionValue
from atlas_ml_platform.modules.inference.application.runtime_cache import (
    ModelRuntimeCache,
    RuntimeKey,
)
from atlas_ml_platform.modules.inference.domain.errors import (
    InferenceError,
    InferenceTimeout,
    InvalidInferenceInput,
    ModelLoadError,
    ModelLoadTimeout,
    PredictionError,
    UntrustedArtifact,
)
from atlas_ml_platform.modules.inference.domain.input import InferenceInput
from atlas_ml_platform.modules.model_registry.application.ports import UnitOfWork
from atlas_ml_platform.modules.model_registry.application.version_use_cases import (
    GetActiveModelVersion,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InferenceResult:
    request_id: UUID
    model_id: UUID
    model_version_id: UUID
    version_number: int
    predictions: list[PredictionValue]
    latency_ms: float


@dataclass(slots=True)
class _InferenceState:
    cache_hit: bool = False


class RunInference:
    def __init__(
        self,
        uow: UnitOfWork,
        store: ArtifactStore,
        runtime_cache: ModelRuntimeCache,
        *,
        trusted_checksums: frozenset[str],
        max_batch_size: int,
        load_timeout_seconds: float,
        inference_timeout_seconds: float,
        auto_trust_artifacts: bool = False,
        tracer: Tracer | None = None,
    ) -> None:
        self._uow = uow
        self._store = store
        self._runtime_cache = runtime_cache
        self._trusted_checksums = trusted_checksums
        self._max_batch_size = max_batch_size
        self._load_timeout_seconds = load_timeout_seconds
        self._inference_timeout_seconds = inference_timeout_seconds
        self._auto_trust_artifacts = auto_trust_artifacts
        self._tracer = tracer

    async def execute(
        self,
        model_id: UUID,
        features: Sequence[Sequence[float]],
        *,
        request_id: UUID | None = None,
    ) -> InferenceResult:
        started = time.perf_counter()
        request_id = request_id or uuid.uuid4()
        state = _InferenceState()
        outcome = "error"
        try:
            result = await self._execute_traced(
                model_id,
                features,
                request_id=request_id,
                state=state,
                started=started,
            )
            outcome = "success"
            return result
        except Exception as exc:
            outcome = _inference_outcome(exc)
            raise
        finally:
            observe_inference(
                outcome=outcome,
                cache_hit=state.cache_hit,
                duration_seconds=time.perf_counter() - started,
            )

    async def _execute_traced(
        self,
        model_id: UUID,
        features: Sequence[Sequence[float]],
        *,
        request_id: UUID,
        state: _InferenceState,
        started: float,
    ) -> InferenceResult:
        tracer = self._tracer or trace.get_tracer(__name__)

        with tracer.start_as_current_span("inference.run") as span:
            span.set_attribute("inference.request_id", str(request_id))
            span.set_attribute("model.id", str(model_id))
            span.set_attribute("inference.batch_size", len(features))

            input_data = InferenceInput.create(
                features,
                max_batch_size=self._max_batch_size,
            )

            with tracer.start_as_current_span("model.lookup") as lookup_span:
                version = await GetActiveModelVersion(self._uow).execute(model_id)
                artifact = await self._uow.artifacts.get_by_uri(version.artifact_uri)
                if artifact is None:
                    raise ArtifactUriNotFound(version.artifact_uri)
                lookup_span.set_attribute("model.version_id", str(version.id))
                lookup_span.set_attribute(
                    "model.version_number", version.version_number
                )
                lookup_span.set_attribute("artifact.id", str(artifact.id))
                lookup_span.set_attribute("artifact.uri", artifact.uri)

            span.set_attribute("model.version_id", str(version.id))
            span.set_attribute("model.version_number", version.version_number)

            if not self._auto_trust_artifacts and (
                artifact.checksum not in self._trusted_checksums
            ):
                raise UntrustedArtifact(
                    f"Artifact {artifact.id} is not in the trusted checksum allowlist"
                )

            key = RuntimeKey(artifact_uri=artifact.uri, checksum=artifact.checksum)
            runtime = await self._runtime_cache.get(key)
            state.cache_hit = runtime is not None
            span.set_attribute("inference.cache_hit", state.cache_hit)

            if runtime is None:
                with tracer.start_as_current_span("artifact.fetch") as fetch_span:
                    try:
                        data = await asyncio.wait_for(
                            read_verified_artifact(artifact, self._store),
                            timeout=self._load_timeout_seconds,
                        )
                    except TimeoutError as exc:
                        raise ModelLoadTimeout(
                            f"Artifact retrieval exceeded {self._load_timeout_seconds}s"
                        ) from exc
                    except ArtifactIntegrityError:
                        raise
                    except InferenceError:
                        raise
                    except Exception as exc:
                        raise ModelLoadError(
                            "Failed to retrieve model artifact"
                        ) from exc
                    fetch_span.set_attribute("artifact.bytes", len(data))

                with tracer.start_as_current_span("model.load") as load_span:
                    runtime = await self._runtime_cache.load(key, data)
                    load_span.set_attribute("artifact.id", str(artifact.id))
                    load_span.set_attribute("artifact.checksum", artifact.checksum)

            try:
                with tracer.start_as_current_span("model.predict") as predict_span:
                    predictions = await asyncio.wait_for(
                        asyncio.to_thread(runtime.predict, input_data.features),
                        timeout=self._inference_timeout_seconds,
                    )
                    predict_span.set_attribute(
                        "inference.predictions_count", len(predictions)
                    )
            except TimeoutError as exc:
                raise InferenceTimeout(
                    f"Inference exceeded {self._inference_timeout_seconds}s"
                ) from exc
            except InferenceError:
                raise
            except Exception as exc:
                raise PredictionError("Model prediction failed") from exc

            span.set_attribute("inference.predictions_count", len(predictions))
            span.set_attribute("inference.outcome", "success")
            span.set_status(StatusCode.OK)

            latency_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "inference_completed",
                extra={
                    "request_id": request_id,
                    "model_id": str(model_id),
                    "version_id": str(version.id),
                    "rows": len(input_data.features),
                    "latency_ms": round(latency_ms, 2),
                    "outcome": "success",
                },
            )
            return InferenceResult(
                request_id=request_id,
                model_id=model_id,
                model_version_id=version.id,
                version_number=version.version_number,
                predictions=predictions,
                latency_ms=latency_ms,
            )


def _inference_outcome(exc: Exception) -> str:
    if isinstance(exc, (InferenceTimeout, ModelLoadTimeout)):
        return "timeout"
    if isinstance(exc, InvalidInferenceInput):
        return "invalid_input"
    return "error"
