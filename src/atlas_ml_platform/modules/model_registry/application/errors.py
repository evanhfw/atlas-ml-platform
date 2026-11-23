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
