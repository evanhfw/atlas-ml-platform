from atlas_ml_platform.modules.model_registry.application.errors import (
    InvalidPagination,
)

MAX_PAGE_SIZE = 100


def validate_pagination(*, limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise InvalidPagination(f"limit must be between 1 and {MAX_PAGE_SIZE}")
    if offset < 0:
        raise InvalidPagination("offset must be greater than or equal to 0")
