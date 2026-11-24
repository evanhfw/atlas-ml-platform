from types import TracebackType
from typing import Self, override

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.modules.artifacts.infrastructure.repository import (
    SQLAlchemyArtifactRepository,
)
from atlas_ml_platform.modules.model_registry.application.ports import UnitOfWork
from atlas_ml_platform.modules.model_registry.infrastructure.deployment_repository import (
    SQLAlchemyModelDeploymentRepository,
)
from atlas_ml_platform.modules.model_registry.infrastructure.model_repository import (
    SQLAlchemyModelRepository,
)
from atlas_ml_platform.modules.model_registry.infrastructure.version_repository import (
    SQLAlchemyModelVersionRepository,
)


class SQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory
        self._session: AsyncSession | None = None
        self._models: SQLAlchemyModelRepository | None = None
        self._versions: SQLAlchemyModelVersionRepository | None = None
        self._deployments: SQLAlchemyModelDeploymentRepository | None = None
        self._artifacts: SQLAlchemyArtifactRepository | None = None

    @property
    @override
    def models(self) -> SQLAlchemyModelRepository:
        if self._models is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._models

    @property
    @override
    def versions(self) -> SQLAlchemyModelVersionRepository:
        if self._versions is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._versions

    @property
    @override
    def deployments(self) -> SQLAlchemyModelDeploymentRepository:
        if self._deployments is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._deployments

    @property
    def artifacts(self) -> SQLAlchemyArtifactRepository:
        if self._artifacts is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._artifacts

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._models = SQLAlchemyModelRepository(self._session)
        self._versions = SQLAlchemyModelVersionRepository(self._session)
        self._deployments = SQLAlchemyModelDeploymentRepository(self._session)
        self._artifacts = SQLAlchemyArtifactRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return

        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
            self._models = None
            self._versions = None
            self._deployments = None
            self._artifacts = None

    @override
    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active")
        await self._session.commit()

    @override
    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active")
        await self._session.rollback()
