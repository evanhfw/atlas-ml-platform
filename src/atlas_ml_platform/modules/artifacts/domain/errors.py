class ArtifactError(Exception):
    """Base error for the artifact domain."""


class InvalidArtifact(ArtifactError):
    """Raised when artifact metadata violates domain rules."""
