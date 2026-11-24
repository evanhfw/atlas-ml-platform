import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass

from atlas_ml_platform.core.metrics import observe_model_load
from atlas_ml_platform.modules.inference.application.ports import (
    ModelRuntime,
    ModelRuntimeLoader,
)
from atlas_ml_platform.modules.inference.domain.errors import (
    InferenceError,
    ModelLoadError,
    ModelLoadTimeout,
)


@dataclass(frozen=True, slots=True)
class RuntimeKey:
    artifact_uri: str
    checksum: str


class ModelRuntimeCache:
    """Process-local LRU cache with single-flight model loading."""

    def __init__(
        self,
        loader: ModelRuntimeLoader,
        *,
        max_entries: int,
        load_timeout_seconds: float,
    ) -> None:
        self._loader: ModelRuntimeLoader = loader
        self._max_entries: int = max_entries
        self._load_timeout_seconds: float = load_timeout_seconds
        self._cache: OrderedDict[RuntimeKey, ModelRuntime] = OrderedDict()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def get(self, key: RuntimeKey) -> ModelRuntime | None:
        async with self._lock:
            runtime = self._cache.get(key)
            if runtime is not None:
                self._cache.move_to_end(key)
            return runtime

    async def load(self, key: RuntimeKey, data: bytes) -> ModelRuntime:
        async with self._lock:
            existing = self._cache.get(key)
            if existing is not None:
                self._cache.move_to_end(key)
                return existing

            started = time.perf_counter()
            try:
                runtime = await asyncio.wait_for(
                    asyncio.to_thread(self._loader.load, data),
                    timeout=self._load_timeout_seconds,
                )
            except TimeoutError as exc:
                observe_model_load(
                    outcome="timeout",
                    duration_seconds=time.perf_counter() - started,
                )
                raise ModelLoadTimeout(
                    f"Model loading exceeded {self._load_timeout_seconds}s"
                ) from exc
            except InferenceError:
                observe_model_load(
                    outcome="error",
                    duration_seconds=time.perf_counter() - started,
                )
                raise
            except Exception as exc:
                observe_model_load(
                    outcome="error",
                    duration_seconds=time.perf_counter() - started,
                )
                raise ModelLoadError("Failed to deserialize model artifact") from exc
            else:
                observe_model_load(
                    outcome="success",
                    duration_seconds=time.perf_counter() - started,
                )

            self._cache[key] = runtime
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_entries:
                _ = self._cache.popitem(last=False)
            return runtime
