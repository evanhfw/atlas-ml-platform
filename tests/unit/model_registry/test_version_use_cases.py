from uuid import UUID, uuid4

import pytest

from atlas_ml_platform.modules.model_registry.application.dto import (
    CreateModelCommand,
    CreateModelVersionCommand,
    ListModelVersionsQuery,
)
from atlas_ml_platform.modules.model_registry.application.errors import (
    ModelNotFound,
    NoActiveVersion,
    VersionNotFound,
    VersionNotReady,
)
from atlas_ml_platform.modules.model_registry.application.model_use_cases import (
    CreateModel,
)
from atlas_ml_platform.modules.model_registry.application.version_use_cases import (
    ActivateModelVersion,
    CreateModelVersion,
    GetActiveModelVersion,
    GetModelVersion,
    ListModelVersions,
    MarkModelVersionReady,
)
from atlas_ml_platform.modules.model_registry.domain import (
    InvalidVersionTransition,
    Model,
    ModelVersion,
    VersionStatus,
)


async def _create_model(uow, name: str = "churn") -> Model:
    return await CreateModel(uow).execute(
        CreateModelCommand(
            name=name,
            framework="sklearn",
            task_type="classification",
        )
    )


async def _create_version(
    uow,
    model_id: UUID,
    artifact_uri: str = "s3://bucket/model.joblib",
) -> ModelVersion:
    return await CreateModelVersion(uow).execute(
        CreateModelVersionCommand(
            model_id=model_id,
            artifact_uri=artifact_uri,
        )
    )


async def test_create_version_allocates_numbers(fake_uow) -> None:
    model = await _create_model(fake_uow)

    first = await _create_version(fake_uow, model.id)
    second = await _create_version(fake_uow, model.id)

    assert first.version_number == 1
    assert second.version_number == 2
    assert first.status is VersionStatus.DRAFT
    assert second.status is VersionStatus.DRAFT


async def test_create_version_requires_model(fake_uow) -> None:
    with pytest.raises(ModelNotFound):
        _ = await _create_version(fake_uow, uuid4())

    assert fake_uow.rolled_back is True


async def test_get_version_is_scoped_to_model(fake_uow) -> None:
    model = await _create_model(fake_uow, "a")
    other = await _create_model(fake_uow, "b")
    version = await _create_version(fake_uow, model.id)

    with pytest.raises(VersionNotFound):
        _ = await GetModelVersion(fake_uow).execute(other.id, version.id)


async def test_get_missing_version(fake_uow) -> None:
    model = await _create_model(fake_uow)

    with pytest.raises(VersionNotFound):
        _ = await GetModelVersion(fake_uow).execute(model.id, uuid4())


async def test_mark_ready_and_activate(fake_uow) -> None:
    model = await _create_model(fake_uow)
    version = await _create_version(fake_uow, model.id)

    ready = await MarkModelVersionReady(fake_uow).execute(model.id, version.id)
    activated = await ActivateModelVersion(fake_uow).execute(model.id, version.id)
    active = await GetActiveModelVersion(fake_uow).execute(model.id)

    assert ready.status is VersionStatus.READY
    assert activated.id == version.id
    assert active.id == version.id
    assert await fake_uow.deployments.get_active_version_id(model.id) == version.id


async def test_activate_requires_ready_version(fake_uow) -> None:
    model = await _create_model(fake_uow)
    version = await _create_version(fake_uow, model.id)

    with pytest.raises(VersionNotReady):
        _ = await ActivateModelVersion(fake_uow).execute(model.id, version.id)

    assert fake_uow.rolled_back is True


async def test_mark_ready_twice_is_rejected(fake_uow) -> None:
    model = await _create_model(fake_uow)
    version = await _create_version(fake_uow, model.id)
    _ = await MarkModelVersionReady(fake_uow).execute(model.id, version.id)

    with pytest.raises(InvalidVersionTransition):
        _ = await MarkModelVersionReady(fake_uow).execute(model.id, version.id)


async def test_get_active_without_deployment(fake_uow) -> None:
    model = await _create_model(fake_uow)

    with pytest.raises(NoActiveVersion):
        _ = await GetActiveModelVersion(fake_uow).execute(model.id)


async def test_list_versions_orders_and_paginates(fake_uow) -> None:
    model = await _create_model(fake_uow)
    for _ in range(3):
        _ = await _create_version(fake_uow, model.id)

    first_page = await ListModelVersions(fake_uow).execute(
        model.id,
        ListModelVersionsQuery(limit=2, offset=0),
    )
    second_page = await ListModelVersions(fake_uow).execute(
        model.id,
        ListModelVersionsQuery(limit=2, offset=2),
    )

    assert [version.version_number for version in first_page] == [3, 2]
    assert [version.version_number for version in second_page] == [1]


async def test_list_versions_requires_model(fake_uow) -> None:
    with pytest.raises(ModelNotFound):
        _ = await ListModelVersions(fake_uow).execute(
            uuid4(),
            ListModelVersionsQuery(),
        )
