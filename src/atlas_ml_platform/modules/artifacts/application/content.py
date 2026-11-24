import asyncio
import hashlib
import time

from atlas_ml_platform.core.metrics import observe_artifact_read
from atlas_ml_platform.modules.artifacts.application.errors import (
    ArtifactIntegrityError,
)
from atlas_ml_platform.modules.artifacts.application.ports import ArtifactStore
from atlas_ml_platform.modules.artifacts.domain.artifact import Artifact


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def read_verified_artifact(artifact: Artifact, store: ArtifactStore) -> bytes:
    """Read artifact bytes and verify the persisted SHA-256 digest."""
    started = time.perf_counter()
    try:
        data = await store.get(artifact.key)
        checksum = await asyncio.to_thread(_sha256_hex, data)
        if checksum != artifact.checksum:
            raise ArtifactIntegrityError(artifact.id)
    except ArtifactIntegrityError:
        observe_artifact_read(
            outcome="integrity_error",
            duration_seconds=time.perf_counter() - started,
        )
        raise
    except Exception:
        observe_artifact_read(
            outcome="error",
            duration_seconds=time.perf_counter() - started,
        )
        raise
    else:
        observe_artifact_read(
            outcome="success",
            duration_seconds=time.perf_counter() - started,
        )
        return data
