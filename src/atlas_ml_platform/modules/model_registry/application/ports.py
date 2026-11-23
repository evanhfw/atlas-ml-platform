from typing import Protocol
from uuid import UUID

from atlas_ml_platform.modules.model_registry.domain import Model, ModelName


class ModelRepository(Protocol):
    """Persistence contract for the model registry aggregate."""

    async def add(self, model: Model) -> None: ...

    async def get(self, model_id: UUID) -> Model | None: ...

    async def get_by_name(self, name: ModelName) -> Model | None: ...

    async def list_models(self, *, limit: int, offset: int) -> list[Model]:
        """Return models ordered by creation time, newest first."""
        ...


class UnitOfWork(Protocol):
    """Request-scoped transaction boundary."""

    @property
    def models(self) -> ModelRepository: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
