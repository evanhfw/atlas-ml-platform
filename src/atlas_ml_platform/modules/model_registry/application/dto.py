from dataclasses import dataclass


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
