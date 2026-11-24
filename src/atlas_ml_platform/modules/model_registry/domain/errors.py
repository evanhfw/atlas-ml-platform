class ModelRegistryError(Exception):
    """Base error for the model registry domain."""


class InvalidModelName(ModelRegistryError):
    """Raised when a model name violates domain rules."""


class InvalidVersionNumber(ModelRegistryError):
    """Raised when a version number is not a positive integer."""


class InvalidArtifactUri(ModelRegistryError):
    """Raised when an artifact URI is empty or invalid."""


class InvalidVersionTransition(ModelRegistryError):
    """Raised when a model version lifecycle transition is not allowed."""
