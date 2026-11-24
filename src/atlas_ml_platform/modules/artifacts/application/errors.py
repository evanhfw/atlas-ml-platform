from uuid import UUID


class ArtifactApplicationError(Exception):
    """Base error for artifact use cases."""


class ArtifactNotFound(ArtifactApplicationError):
    def __init__(self, artifact_id: UUID) -> None:
        super().__init__(f"Artifact not found: {artifact_id}")
        self.artifact_id: UUID = artifact_id


class ArtifactUriNotFound(ArtifactApplicationError):
    def __init__(self, uri: str) -> None:
        super().__init__(f"Artifact not found for URI: {uri}")
        self.uri: str = uri


class ArtifactTooLarge(ArtifactApplicationError):
    def __init__(self, max_size_bytes: int) -> None:
        super().__init__(f"Artifact exceeds the maximum size of {max_size_bytes} bytes")
        self.max_size_bytes: int = max_size_bytes


class UnsupportedArtifactType(ArtifactApplicationError):
    def __init__(self, content_type: str) -> None:
        super().__init__(f"Unsupported artifact content type: {content_type}")
        self.content_type: str = content_type


class ArtifactIntegrityError(ArtifactApplicationError):
    def __init__(self, artifact_id: UUID) -> None:
        super().__init__(f"Artifact checksum verification failed: {artifact_id}")
        self.artifact_id: UUID = artifact_id
