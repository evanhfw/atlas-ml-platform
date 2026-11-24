import hashlib
from uuid import UUID

import pytest

from atlas_ml_platform.modules.artifacts.application.ports import StoredArtifact
from atlas_ml_platform.modules.artifacts.domain.artifact import Artifact


class FakeArtifactStore:
    def __init__(self, *, bucket: str = "test-bucket") -> None:
        self._bucket: str = bucket
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.put_keys: list[str] = []
        self.deleted: list[str] = []
        self.get_calls: int = 0

    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredArtifact:
        self.objects[key] = (data, content_type)
        self.put_keys.append(key)
        return StoredArtifact(
            key=key,
            uri=f"s3://{self._bucket}/{key}",
            checksum=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type=content_type,
        )

    async def get(self, key: str) -> bytes:
        self.get_calls += 1
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        del self.objects[key]
        self.deleted.append(key)


class FakeArtifactRepository:
    """Stages writes until the unit of work commits, like a transaction."""

    def __init__(self) -> None:
        self.persisted: dict[UUID, Artifact] = {}
        self.pending: dict[UUID, Artifact] = {}
        self.fail_add: bool = False

    async def add(self, artifact: Artifact) -> None:
        if self.fail_add:
            raise RuntimeError("add failed")
        self.pending[artifact.id] = artifact

    async def get(self, artifact_id: UUID) -> Artifact | None:
        return self.persisted.get(artifact_id)

    async def get_by_uri(self, uri: str) -> Artifact | None:
        return next(
            (artifact for artifact in self.persisted.values() if artifact.uri == uri),
            None,
        )


class FakeUnitOfWork:
    def __init__(self) -> None:
        self._artifacts: FakeArtifactRepository = FakeArtifactRepository()
        self.committed: bool = False
        self.rolled_back: bool = False
        self.fail_commit: bool = False

    @property
    def artifacts(self) -> FakeArtifactRepository:
        return self._artifacts

    async def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self._artifacts.persisted.update(self._artifacts.pending)
        self._artifacts.pending.clear()
        self.committed = True

    async def rollback(self) -> None:
        self._artifacts.pending.clear()
        self.rolled_back = True


@pytest.fixture
def fake_store() -> FakeArtifactStore:
    return FakeArtifactStore()


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()
