from uuid import UUID

import pytest

from atlas_ml_platform.modules.artifacts.application.ports import ArtifactRepository
from atlas_ml_platform.modules.artifacts.domain import Artifact
from atlas_ml_platform.modules.model_registry.application.ports import (
    ModelDeploymentRepository,
    ModelRepository,
    ModelVersionRepository,
)
from atlas_ml_platform.modules.model_registry.domain import (
    Model,
    ModelName,
    ModelVersion,
)


class FakeModelRepository:
    def __init__(self) -> None:
        self._models: dict[UUID, Model] = {}

    async def add(self, model: Model) -> None:
        self._models[model.id] = model

    async def get(self, model_id: UUID) -> Model | None:
        return self._models.get(model_id)

    async def get_by_name(self, name: ModelName) -> Model | None:
        return next(
            (model for model in self._models.values() if model.name == name),
            None,
        )

    async def list_models(self, *, limit: int, offset: int) -> list[Model]:
        models = sorted(
            self._models.values(),
            key=lambda model: model.created_at,
            reverse=True,
        )
        return models[offset : offset + limit]


class FakeModelVersionRepository:
    def __init__(self) -> None:
        self._versions: dict[UUID, ModelVersion] = {}

    async def add(self, version: ModelVersion) -> None:
        self._versions[version.id] = version

    async def get(
        self,
        model_id: UUID,
        version_id: UUID,
    ) -> ModelVersion | None:
        version = self._versions.get(version_id)
        if version is None or version.model_id != model_id:
            return None
        return version

    async def list_versions(
        self,
        *,
        model_id: UUID,
        limit: int,
        offset: int,
    ) -> list[ModelVersion]:
        versions = sorted(
            (
                version
                for version in self._versions.values()
                if version.model_id == model_id
            ),
            key=lambda version: version.version_number,
            reverse=True,
        )
        return versions[offset : offset + limit]

    async def next_version_number(self, model_id: UUID) -> int:
        numbers = [
            version.version_number
            for version in self._versions.values()
            if version.model_id == model_id
        ]
        return max(numbers, default=0) + 1

    async def save(self, version: ModelVersion) -> None:
        self._versions[version.id] = version


class FakeModelDeploymentRepository:
    def __init__(self) -> None:
        self._active: dict[UUID, UUID] = {}

    async def get_active_version_id(self, model_id: UUID) -> UUID | None:
        return self._active.get(model_id)

    async def activate(self, model_id: UUID, version_id: UUID) -> None:
        self._active[model_id] = version_id


class FakeArtifactRepository:
    def __init__(self) -> None:
        self._artifacts: dict[UUID, Artifact] = {}

    async def add(self, artifact: Artifact) -> None:
        self._artifacts[artifact.id] = artifact

    async def get(self, artifact_id: UUID) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    async def get_by_uri(self, uri: str) -> Artifact | None:
        return next(
            (artifact for artifact in self._artifacts.values() if artifact.uri == uri),
            None,
        )


class FakeUnitOfWork:
    def __init__(self) -> None:
        self._models: FakeModelRepository = FakeModelRepository()
        self._versions: FakeModelVersionRepository = FakeModelVersionRepository()
        self._deployments: FakeModelDeploymentRepository = (
            FakeModelDeploymentRepository()
        )
        self._artifacts: FakeArtifactRepository = FakeArtifactRepository()
        self.committed: bool = False
        self.rolled_back: bool = False

    @property
    def models(self) -> ModelRepository:
        return self._models

    @property
    def versions(self) -> ModelVersionRepository:
        return self._versions

    @property
    def deployments(self) -> ModelDeploymentRepository:
        return self._deployments

    @property
    def artifacts(self) -> ArtifactRepository:
        return self._artifacts

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()
