from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_ml_platform.modules.model_registry.infrastructure import (
    SQLAlchemyUnitOfWork,
)


async def get_unit_of_work(
    request: Request,
) -> AsyncIterator[SQLAlchemyUnitOfWork]:
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )

    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        yield uow


UnitOfWorkDep = Annotated[SQLAlchemyUnitOfWork, Depends(get_unit_of_work)]
