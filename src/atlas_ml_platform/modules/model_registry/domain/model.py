import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Self, override

from atlas_ml_platform.modules.model_registry.domain.errors import InvalidModelName


@dataclass(frozen=True, slots=True)
class ModelName:
    """A validated, normalized model name."""

    value: str

    MAX_LENGTH: ClassVar[int] = 255

    def __post_init__(self) -> None:
        # Type hints are not enforced at runtime; fail clearly for untyped callers.
        if not isinstance(self.value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise InvalidModelName("Model name must be a string")

        normalized = self.value.strip()

        if not normalized:
            raise InvalidModelName("Model name must not be empty")

        if len(normalized) > self.MAX_LENGTH:
            raise InvalidModelName(
                f"Model name must be at most {self.MAX_LENGTH} characters"
            )

        if any(unicodedata.category(ch) in {"Cc", "Cf"} for ch in normalized):
            raise InvalidModelName(
                "Model name must not contain control or format characters"
            )

        object.__setattr__(self, "value", normalized)

    @override
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, eq=False)
class Model:
    """A registered model entity, identified by its ID."""

    id: uuid.UUID
    name: ModelName
    description: str | None
    framework: str
    task_type: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: ModelName,
        framework: str,
        task_type: str,
        description: str | None = None,
    ) -> Self:
        now = datetime.now(UTC)
        return cls(
            id=uuid.uuid4(),
            name=name,
            framework=framework,
            task_type=task_type,
            description=description,
            created_at=now,
            updated_at=now,
        )

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Model):
            return NotImplemented
        return self.id == other.id

    @override
    def __hash__(self) -> int:
        return hash(self.id)
