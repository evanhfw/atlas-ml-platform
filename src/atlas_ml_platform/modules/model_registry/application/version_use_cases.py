from uuid import UUID

from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelVersionCommand,
    ListModelVersionsQuery,
)
from atlas_ml_platform.modules.model_registry.application.errors import (
    ModelNotFound,
    NoActiveVersion,
    VersionNotFound,
    VersionNotReady,
)
from atlas_ml_platform.modules.model_registry.application.pagination import (
    validate_pagination,
)
from atlas_ml_platform.modules.model_registry.application.ports import UnitOfWork
from atlas_ml_platform.modules.model_registry.domain import (
    ModelVersion,
    VersionStatus,
)


class CreateModelVersion:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, command: CreateModelVersionCommand) -> ModelVersion:
        try:
            if await self._uow.models.get(command.model_id) is None:
                raise ModelNotFound(command.model_id)

            version_number = await self._uow.versions.next_version_number(
                command.model_id
            )
            version = ModelVersion.create(
                model_id=command.model_id,
                version_number=version_number,
                artifact_uri=command.artifact_uri,
            )
            await self._uow.versions.add(version)
            await self._uow.commit()
            return version
        except Exception:
            await self._uow.rollback()
            raise


class GetModelVersion:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, model_id: UUID, version_id: UUID) -> ModelVersion:
        version = await self._uow.versions.get(model_id, version_id)
        if version is None:
            raise VersionNotFound(model_id, version_id)
        return version


class ListModelVersions:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(
        self,
        model_id: UUID,
        query: ListModelVersionsQuery,
    ) -> list[ModelVersion]:
        validate_pagination(limit=query.limit, offset=query.offset)

        if await self._uow.models.get(model_id) is None:
            raise ModelNotFound(model_id)

        return await self._uow.versions.list_versions(
            model_id=model_id,
            limit=query.limit,
            offset=query.offset,
        )


class MarkModelVersionReady:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, model_id: UUID, version_id: UUID) -> ModelVersion:
        try:
            version = await self._uow.versions.get(model_id, version_id)
            if version is None:
                raise VersionNotFound(model_id, version_id)

            ready = version.mark_ready()
            await self._uow.versions.save(ready)
            await self._uow.commit()
            return ready
        except Exception:
            await self._uow.rollback()
            raise


class ActivateModelVersion:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, model_id: UUID, version_id: UUID) -> ModelVersion:
        try:
            if await self._uow.models.get(model_id) is None:
                raise ModelNotFound(model_id)

            version = await self._uow.versions.get(model_id, version_id)
            if version is None:
                raise VersionNotFound(model_id, version_id)

            if version.status is not VersionStatus.READY:
                raise VersionNotReady(version.id, version.status.value)

            await self._uow.deployments.activate(model_id, version_id)
            await self._uow.commit()
            return version
        except Exception:
            await self._uow.rollback()
            raise


class GetActiveModelVersion:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow: UnitOfWork = uow

    async def execute(self, model_id: UUID) -> ModelVersion:
        if await self._uow.models.get(model_id) is None:
            raise ModelNotFound(model_id)

        version_id = await self._uow.deployments.get_active_version_id(model_id)
        if version_id is None:
            raise NoActiveVersion(model_id)

        version = await self._uow.versions.get(model_id, version_id)
        if version is None:
            raise VersionNotFound(model_id, version_id)
        return version
