class ModelRegistryError(Exception):
    """Base error for the model registry domain."""


class InvalidModelName(ModelRegistryError):
    """Raised when a model name violates domain rules."""
