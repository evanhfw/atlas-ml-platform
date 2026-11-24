import hashlib

import pytest

from atlas_ml_platform.modules.inference.application.runtime_cache import (
    RuntimeKey,
)
from atlas_ml_platform.modules.inference.domain.errors import (
    ModelLoadError,
    ModelLoadTimeout,
)


def _key(name: str) -> RuntimeKey:
    return RuntimeKey(
        artifact_uri=f"s3://bucket/{name}",
        checksum=hashlib.sha256(name.encode()).hexdigest(),
    )


async def test_same_key_uses_cached_runtime_without_reloading(
    build_cache,
    fake_loader,
) -> None:
    cache = build_cache(fake_loader)
    key = _key("a")

    first = await cache.load(key, b"first-bytes")
    second = await cache.load(key, b"second-bytes")

    assert second is first
    assert fake_loader.calls == [b"first-bytes"]


async def test_different_checksum_for_same_artifact_reloads(
    build_cache,
    fake_loader,
) -> None:
    cache = build_cache(fake_loader)
    first_key = _key("a")
    second_key = RuntimeKey(
        artifact_uri=first_key.artifact_uri,
        checksum=hashlib.sha256(b"different").hexdigest(),
    )

    first = await cache.load(first_key, b"first-bytes")
    second = await cache.load(second_key, b"second-bytes")

    assert second is not first
    assert fake_loader.calls == [b"first-bytes", b"second-bytes"]
    assert await cache.get(first_key) is first
    assert await cache.get(second_key) is second


async def test_lru_evicts_least_recently_used_entry(
    build_cache,
    fake_loader,
) -> None:
    cache = build_cache(fake_loader, max_entries=2)
    key_a, key_b, key_c = _key("a"), _key("b"), _key("c")

    runtime_a = await cache.load(key_a, b"a")
    _ = await cache.load(key_b, b"b")
    # Touch A so B becomes the least recently used entry.
    assert await cache.get(key_a) is runtime_a

    runtime_c = await cache.load(key_c, b"c")

    assert await cache.get(key_b) is None
    assert await cache.get(key_a) is runtime_a
    assert await cache.get(key_c) is runtime_c
    _ = await cache.load(key_b, b"b")
    assert len(fake_loader.calls) == 4


async def test_loader_failure_is_not_cached(build_cache, fake_loader) -> None:
    cache = build_cache(fake_loader)
    key = _key("a")
    fake_loader.error = ModelLoadError("bad artifact")

    with pytest.raises(ModelLoadError, match="bad artifact"):
        _ = await cache.load(key, b"broken-bytes")

    assert await cache.get(key) is None

    fake_loader.error = None
    runtime = await cache.load(key, b"good-bytes")

    assert fake_loader.calls == [b"broken-bytes", b"good-bytes"]
    assert await cache.get(key) is runtime


async def test_loader_timeout_raises_and_caches_nothing(
    build_cache,
    fake_loader,
) -> None:
    fake_loader.delay_seconds = 0.2
    cache = build_cache(fake_loader, load_timeout_seconds=0.02)
    key = _key("a")

    with pytest.raises(ModelLoadTimeout):
        _ = await cache.load(key, b"slow-bytes")

    assert await cache.get(key) is None
