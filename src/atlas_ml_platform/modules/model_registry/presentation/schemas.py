from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from atlas_ml_platform.modules.model_registry.domain import Model


class ModelCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    framework: str = Field(min_length=1, max_length=64)
    task_type: str = Field(min_length=1, max_length=64)


class ModelRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    framework: str
    task_type: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, model: Model) -> Self:
        return cls(
            id=model.id,
            name=model.name.value,
            description=model.description,
            framework=model.framework,
            task_type=model.task_type,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class ModelList(BaseModel):
    items: list[ModelRead]
    limit: int
    offset: int
