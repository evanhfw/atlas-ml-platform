import uuid
from datetime import UTC, datetime

import pytest

from atlas_ml_platform.modules.model_registry.domain import (
    InvalidModelName,
    Model,
    ModelName,
)


def test_model_name_trims_whitespace() -> None:
    assert ModelName("  churn  ").value == "churn"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_model_name_rejects_empty(value: str) -> None:
    with pytest.raises(InvalidModelName):
        ModelName(value)


@pytest.mark.parametrize(
    "value",
    ["a\x00b", "a\nb", "a\tb", "a\u200bb", "a\u202eb"],
)
def test_model_name_rejects_control_characters(value: str) -> None:
    with pytest.raises(InvalidModelName):
        ModelName(value)


def test_model_name_accepts_max_length() -> None:
    name = ModelName("a" * 255)

    assert len(name.value) == 255


def test_model_name_rejects_too_long() -> None:
    with pytest.raises(InvalidModelName):
        ModelName("a" * 256)


def test_model_name_rejects_non_string() -> None:
    with pytest.raises(InvalidModelName):
        ModelName(123)  # type: ignore[arg-type]


def test_model_name_str() -> None:
    assert str(ModelName("churn")) == "churn"


def test_model_create_sets_identity_and_timestamps() -> None:
    before = datetime.now(UTC)

    model = Model.create(
        name=ModelName("churn"),
        description="Predict customer churn",
        framework="sklearn",
        task_type="classification",
    )

    after = datetime.now(UTC)

    assert isinstance(model.id, uuid.UUID)
    assert model.created_at.tzinfo is not None
    assert before <= model.created_at <= after
    assert model.created_at == model.updated_at


def test_model_identity_is_based_on_id() -> None:
    model_id = uuid.uuid4()
    now = datetime.now(UTC)

    first = Model(
        id=model_id,
        name=ModelName("churn"),
        description="first",
        framework="sklearn",
        task_type="classification",
        created_at=now,
        updated_at=now,
    )
    second = Model(
        id=model_id,
        name=ModelName("fraud"),
        description="second",
        framework="pytorch",
        task_type="regression",
        created_at=now,
        updated_at=now,
    )

    assert first == second
    assert hash(first) == hash(second)


def test_models_with_different_ids_are_not_equal() -> None:
    first = Model.create(
        name=ModelName("churn"),
        framework="sklearn",
        task_type="classification",
    )
    second = Model.create(
        name=ModelName("fraud"),
        framework="sklearn",
        task_type="classification",
    )

    assert first != second
