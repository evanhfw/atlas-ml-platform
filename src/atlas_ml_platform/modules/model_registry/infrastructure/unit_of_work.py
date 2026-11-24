from types import TracebackType
from typing import Self, override

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.modules.model_registry.application.ports import UnitOfWork
from atlas_ml_platform.modules.model_registry.infrastructure.repository import (
    SQLAlchemyModelRepository,
)


class SQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory
        self._session: AsyncSession | None = None
        self._models: SQLAlchemyModelRepository | None = None

    @property
    @override
    def models(self) -> SQLAlchemyModelRepository:
        if self._models is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._models

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._models = SQLAlchemyModelRepository(self._session)
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
