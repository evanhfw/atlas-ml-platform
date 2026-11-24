import asyncio
from uuid import UUID

import pytest

from atlas_ml_platform.modules.artifacts.application.errors import (
    ArtifactIntegrityError,
    ArtifactUriNotFound,
)
from atlas_ml_platform.modules.inference.domain.errors import (
    InferenceTimeout,
    ModelLoadTimeout,
    PredictionError,
    UntrustedArtifact,
)
from atlas_ml_platform.modules.model_registry.application.errors import NoActiveVersion

ROWS = [[1.0, 2.0], [3.0, 4.0]]


async def test_execute_returns_predictions_and_reports_version_identity(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    runtime = wired_loader.runtime
    runtime.predictions = [1, 0]
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    result = await use_case.execute(seed.model.id, ROWS)

    assert result.predictions == [1, 0]
    assert result.model_id == seed.model.id
    assert result.model_version_id == seed.version.id
    assert result.version_number == 1
    assert isinstance(result.request_id, UUID)
    assert result.latency_ms >= 0.0
    assert runtime.calls == [((1.0, 2.0), (3.0, 4.0))]
    assert wired_loader.calls == [b"model-bytes"]
    assert fake_store.get_calls == 1


async def test_second_execute_hits_cache_without_refetch_or_reload(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    runtime = wired_loader.runtime
    runtime.predictions = [1]
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    first = await use_case.execute(seed.model.id, [[1.0, 2.0]])
    second = await use_case.execute(seed.model.id, [[1.0, 2.0]])

    assert first.predictions == second.predictions == [1]
    assert fake_store.get_calls == 1
    assert wired_loader.calls == [b"model-bytes"]
    assert len(runtime.calls) == 2


async def test_untrusted_checksum_is_rejected_before_reading_artifact(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums=frozenset(),
    )

    with pytest.raises(UntrustedArtifact):
        _ = await use_case.execute(seed.model.id, ROWS)

    assert fake_store.get_calls == 0
    assert wired_loader.calls == []


async def test_corrupt_artifact_bytes_raise_integrity_error(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    seed = deploy_model(b"trusted-model-bytes")
    fake_store.objects[seed.artifact.key] = b"tampered-model-bytes"
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    with pytest.raises(ArtifactIntegrityError) as exc_info:
        _ = await use_case.execute(seed.model.id, ROWS)

    assert exc_info.value.artifact_id == seed.artifact.id
    assert wired_loader.calls == []


async def test_missing_artifact_metadata_raises_uri_not_found(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    seed = deploy_model(b"model-bytes")
    fake_uow.artifacts.by_uri.clear()
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    with pytest.raises(ArtifactUriNotFound):
        _ = await use_case.execute(seed.model.id, ROWS)

    assert fake_store.get_calls == 0


async def test_prediction_failure_raises_prediction_error(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    runtime = wired_loader.runtime
    runtime.error = RuntimeError("estimator exploded")
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    with pytest.raises(PredictionError):
        _ = await use_case.execute(seed.model.id, ROWS)


async def test_model_without_active_version_raises_no_active_version(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    seed = deploy_model(b"model-bytes", active=False)
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    with pytest.raises(NoActiveVersion):
        _ = await use_case.execute(seed.model.id, ROWS)

    assert fake_store.get_calls == 0


async def test_artifact_retrieval_timeout_raises_load_timeout(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    fake_store.delay_seconds = 0.2
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
        load_timeout_seconds=0.02,
    )

    with pytest.raises(ModelLoadTimeout):
        _ = await use_case.execute(seed.model.id, ROWS)

    assert wired_loader.calls == []


async def test_inference_timeout_raises_inference_timeout(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    runtime = wired_loader.runtime
    runtime.delay_seconds = 0.2
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
        inference_timeout_seconds=0.02,
    )

    with pytest.raises(InferenceTimeout):
        _ = await use_case.execute(seed.model.id, ROWS)


async def test_slow_prediction_does_not_block_the_event_loop(
    fake_uow,
    fake_store,
    wired_loader,
    deploy_model,
    build_cache,
    run_inference,
) -> None:
    runtime = wired_loader.runtime
    runtime.predictions = [7]
    runtime.delay_seconds = 0.3
    seed = deploy_model(b"model-bytes")
    cache = build_cache(wired_loader)
    use_case = run_inference(
        fake_uow,
        fake_store,
        cache,
        trusted_checksums={seed.artifact.checksum},
    )

    prediction = asyncio.create_task(use_case.execute(seed.model.id, [[1.0, 2.0]]))
    for _ in range(200):
        if runtime.started.is_set():
            break
        await asyncio.sleep(0.005)

    assert runtime.started.is_set(), "predictor never started"
    assert not prediction.done(), "event loop was blocked while predicting"

    # A heartbeat coroutine must get a turn before the prediction returns.
    heartbeat_ran = False

    async def heartbeat() -> None:
        nonlocal heartbeat_ran
        await asyncio.sleep(0)
        heartbeat_ran = True

    await asyncio.wait_for(heartbeat(), timeout=0.1)

    assert heartbeat_ran is True
    assert not prediction.done()
    result = await prediction
    assert result.predictions == [7]
