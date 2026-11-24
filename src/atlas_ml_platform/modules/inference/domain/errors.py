class InferenceError(Exception):
    """Base error for inference execution."""


class InvalidInferenceInput(InferenceError):
    """Raised when the feature matrix is empty, ragged, or non-finite."""


class UntrustedArtifact(InferenceError):
    """Raised when an artifact checksum is not in the trusted allowlist."""


class ModelLoadError(InferenceError):
    """Raised when an artifact cannot be deserialized into a runtime."""


class ModelLoadTimeout(InferenceError):
    """Raised when artifact retrieval or deserialization exceeds its deadline."""


class PredictionError(InferenceError):
    """Raised when the runtime fails while producing predictions."""


class InferenceTimeout(InferenceError):
    """Raised when prediction execution exceeds its deadline."""
