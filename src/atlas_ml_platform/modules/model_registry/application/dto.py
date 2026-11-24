from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateModelCommand:
    name: str
    framework: str
    task_type: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ListModelsQuery:
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class CreateModelVersionCommand:
    model_id: UUID
    artifact_uri: str


@dataclass(frozen=True, slots=True)
class ListModelVersionsQuery:
    limit: int = 20
    offset: int = 0
