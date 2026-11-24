from typing import Protocol
from uuid import UUID

from atlas_ml_platform.modules.artifacts.application.ports import ArtifactRepository
from atlas_ml_platform.modules.model_registry.domain import (
    Model,
    ModelName,
    ModelVersion,
)


class ModelRepository(Protocol):
    """Persistence contract for the model registry aggregate."""

    async def add(self, model: Model) -> None: ...

    async def get(self, model_id: UUID) -> Model | None: ...

    async def get_by_name(self, name: ModelName) -> Model | None: ...

    async def list_models(self, *, limit: int, offset: int) -> list[Model]:
        """Return models ordered by creation time, newest first."""
        ...


class ModelVersionRepository(Protocol):
    """Persistence contract for immutable model versions."""

    async def add(self, version: ModelVersion) -> None: ...

    async def get(
        self,
        model_id: UUID,
        version_id: UUID,
    ) -> ModelVersion | None: ...

    async def list_versions(
        self,
        *,
        model_id: UUID,
        limit: int,
        offset: int,
    ) -> list[ModelVersion]:
        """Return versions ordered by version number, newest first."""
        ...

    async def next_version_number(self, model_id: UUID) -> int:
        """Lock the model row and return the next version number."""
        ...

    async def save(self, version: ModelVersion) -> None: ...


class ModelDeploymentRepository(Protocol):
    """Persistence contract for active model version selection."""

    async def get_active_version_id(self, model_id: UUID) -> UUID | None: ...

    async def activate(self, model_id: UUID, version_id: UUID) -> None: ...


class UnitOfWork(Protocol):
    """Request-scoped transaction boundary."""

    @property
    def models(self) -> ModelRepository: ...

    @property
    def versions(self) -> ModelVersionRepository: ...

    @property
    def deployments(self) -> ModelDeploymentRepository: ...

    @property
    def artifacts(self) -> ArtifactRepository: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
