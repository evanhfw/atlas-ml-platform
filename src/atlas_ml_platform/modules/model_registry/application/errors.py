from uuid import UUID


class ApplicationError(Exception):
    """Base error for model registry use cases."""


class ModelNameAlreadyExists(ApplicationError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Model name already exists: {name}")
        self.name: str = name


class ModelNotFound(ApplicationError):
    def __init__(self, model_id: UUID) -> None:
        super().__init__(f"Model not found: {model_id}")
        self.model_id: UUID = model_id


class InvalidPagination(ApplicationError):
    """Raised when pagination parameters are outside the accepted range."""


class VersionNotFound(ApplicationError):
    def __init__(self, model_id: UUID, version_id: UUID) -> None:
        super().__init__(f"Model version not found: {model_id}/{version_id}")
        self.model_id: UUID = model_id
        self.version_id: UUID = version_id


class VersionNumberConflict(ApplicationError):
    def __init__(self, model_id: UUID) -> None:
        super().__init__(f"Version number conflict for model: {model_id}")
        self.model_id: UUID = model_id


class VersionNotReady(ApplicationError):
    def __init__(self, version_id: UUID, status: str) -> None:
        super().__init__(f"Model version {version_id} is not ready (status={status})")
        self.version_id: UUID = version_id
        self.status: str = status


class NoActiveVersion(ApplicationError):
    def __init__(self, model_id: UUID) -> None:
        super().__init__(f"Model has no active version: {model_id}")
        self.model_id: UUID = model_id
