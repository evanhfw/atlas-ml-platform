import asyncio
import hashlib
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

import pytest

from atlas_ml_platform.modules.artifacts.application.ports import StoredArtifact
from atlas_ml_platform.modules.artifacts.domain.artifact import Artifact
from atlas_ml_platform.modules.inference.application.ports import (
    ModelRuntime,
    PredictionValue,
)
from atlas_ml_platform.modules.inference.application.runtime_cache import (
    ModelRuntimeCache,
)
from atlas_ml_platform.modules.inference.application.use_cases import RunInference
from atlas_ml_platform.modules.model_registry.application.ports import UnitOfWork
from atlas_ml_platform.modules.model_registry.domain import (
    Model,
    ModelName,
    ModelVersion,
)


class FakeModelRuntime:
    """Synchronous runtime whose behaviour each test can configure."""

    def __init__(self, predictions: Sequence[PredictionValue] | None = None) -> None:
        self.predictions: list[PredictionValue] = (
            list(predictions) if predictions is not None else [0]
        )
        self.error: Exception | None = None
        self.delay_seconds: float = 0.0
        self.calls: list[tuple[tuple[float, ...], ...]] = []
        self.started: threading.Event = threading.Event()

    def predict(
        self,
        features: Sequence[Sequence[float]],
    ) -> list[PredictionValue]:
        self.started.set()
        self.calls.append(tuple(tuple(row) for row in features))
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        return list(self.predictions)


class FakeRuntimeLoader:
    """ModelRuntimeLoader that records exactly which bytes it deserialized."""

    def __init__(self, runtime: ModelRuntime | None = None) -> None:
        self.runtime: ModelRuntime | None = runtime
        self.calls: list[bytes] = []
        self.error: Exception | None = None
        self.delay_seconds: float = 0.0

    def load(self, data: bytes) -> ModelRuntime:
        self.calls.append(data)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        return self.runtime if self.runtime is not None else FakeModelRuntime()


class FakeArtifactStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.get_calls: int = 0
        self.delay_seconds: float = 0.0

    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredArtifact:
        self.objects[key] = data
        return StoredArtifact(
            key=key,
            uri=f"s3://test-bucket/{key}",
            checksum=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type=content_type,
        )

    async def get(self, key: str) -> bytes:
        self.get_calls += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return self.objects[key]

    async def delete(self, key: str) -> None:
        del self.objects[key]


class FakeModelRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Model] = {}

    async def get(self, model_id: UUID) -> Model | None:
        return self.by_id.get(model_id)


class FakeModelVersionRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, ModelVersion] = {}

    async def get(
        self,
        model_id: UUID,
        version_id: UUID,
    ) -> ModelVersion | None:
        version = self.by_id.get(version_id)
        if version is None or version.model_id != model_id:
            return None
        return version


class FakeModelDeploymentRepository:
    def __init__(self) -> None:
        self.active: dict[UUID, UUID] = {}

    async def get_active_version_id(self, model_id: UUID) -> UUID | None:
        return self.active.get(model_id)


class FakeArtifactRepository:
    def __init__(self) -> None:
        self.by_uri: dict[str, Artifact] = {}

    async def get_by_uri(self, uri: str) -> Artifact | None:
        return self.by_uri.get(uri)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.models: FakeModelRepository = FakeModelRepository()
        self.versions: FakeModelVersionRepository = FakeModelVersionRepository()
        self.deployments: FakeModelDeploymentRepository = (
            FakeModelDeploymentRepository()
        )
        self.artifacts: FakeArtifactRepository = FakeArtifactRepository()


@dataclass(frozen=True, slots=True)
class SeededModel:
    model: Model
    version: ModelVersion
    artifact: Artifact


@pytest.fixture
def fake_store() -> FakeArtifactStore:
    return FakeArtifactStore()


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def fake_loader() -> FakeRuntimeLoader:
    """Loader that returns a fresh runtime per call, for cache tests."""

    return FakeRuntimeLoader()


@pytest.fixture
def fake_runtime() -> FakeModelRuntime:
    return FakeModelRuntime()


@pytest.fixture
def wired_loader(fake_runtime: FakeModelRuntime) -> FakeRuntimeLoader:
    """Loader whose deserialized runtime the test can observe and configure."""

    return FakeRuntimeLoader(fake_runtime)


@pytest.fixture
def deploy_model(
    fake_uow: FakeUnitOfWork,
    fake_store: FakeArtifactStore,
) -> Callable[..., SeededModel]:
    """Register an artifact and a version, activating it unless asked not to."""

    def _deploy(data: bytes, *, active: bool = True) -> SeededModel:
        artifact = Artifact.create(
            id=uuid4(),
            key=f"artifacts/{uuid4()}",
            uri=f"s3://test-bucket/artifacts/{uuid4()}",
            checksum=hashlib.sha256(data).hexdigest(),
            size_bytes=max(len(data), 1),
            content_type="application/x-joblib",
        )
        fake_store.objects[artifact.key] = data
        fake_uow.artifacts.by_uri[artifact.uri] = artifact

        model = Model.create(
            name=ModelName(f"model-{uuid4().hex[:8]}"),
            framework="sklearn",
            task_type="classification",
        )
        fake_uow.models.by_id[model.id] = model

        version = ModelVersion.create(
            model_id=model.id,
            version_number=1,
            artifact_uri=artifact.uri,
        )
        fake_uow.versions.by_id[version.id] = version
        if active:
            fake_uow.deployments.active[model.id] = version.id

        return SeededModel(model=model, version=version, artifact=artifact)

    return _deploy


@pytest.fixture
def build_cache() -> Callable[..., ModelRuntimeCache]:
    def _build(
        loader: FakeRuntimeLoader,
        *,
        max_entries: int = 8,
        load_timeout_seconds: float = 1.0,
    ) -> ModelRuntimeCache:
        return ModelRuntimeCache(
            loader,
            max_entries=max_entries,
            load_timeout_seconds=load_timeout_seconds,
        )

    return _build


@pytest.fixture
def run_inference() -> Callable[..., RunInference]:
    def _build(
        uow: FakeUnitOfWork,
        store: FakeArtifactStore,
        runtime_cache: ModelRuntimeCache,
        *,
        trusted_checksums: frozenset[str] | None = None,
        max_batch_size: int = 8,
        load_timeout_seconds: float = 1.0,
        inference_timeout_seconds: float = 1.0,
    ) -> RunInference:
        return RunInference(
            cast(UnitOfWork, uow),
            store,
            runtime_cache,
            trusted_checksums=trusted_checksums or frozenset(),
            max_batch_size=max_batch_size,
            load_timeout_seconds=load_timeout_seconds,
            inference_timeout_seconds=inference_timeout_seconds,
        )

    return _build
