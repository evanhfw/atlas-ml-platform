import pytest
from pydantic import ValidationError

from atlas_ml_platform.config import Settings

TEST_DATABASE_URL = (
    "postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_test"
)


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        DATABASE_URL=TEST_DATABASE_URL,
        **overrides,
    )


@pytest.mark.parametrize("value", ["debug", "WaRnInG"])
def test_log_level_is_normalized_to_uppercase(value: str) -> None:
    assert _settings(LOG_LEVEL=value).LOG_LEVEL == value.upper()


@pytest.mark.parametrize("value", ["verbose", "not-a-level"])
def test_unsupported_log_level_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        _ = _settings(LOG_LEVEL=value)


@pytest.mark.parametrize("app_env", ["development", "testing"])
def test_auto_trust_policy_is_accepted_outside_production(app_env: str) -> None:
    settings = _settings(APP_ENV=app_env, ARTIFACT_TRUST_POLICY="auto")

    assert settings.ARTIFACT_TRUST_POLICY == "auto"


def test_production_rejects_auto_trust_policy() -> None:
    with pytest.raises(ValidationError):
        _ = _settings(APP_ENV="production", ARTIFACT_TRUST_POLICY="auto")


def test_production_accepts_allowlist_trust_policy() -> None:
    settings = _settings(APP_ENV="production", ARTIFACT_TRUST_POLICY="allowlist")

    assert settings.ARTIFACT_TRUST_POLICY == "allowlist"


def test_artifact_trust_policy_defaults_to_allowlist() -> None:
    # Security posture, not a cosmetic default: silently switching to "auto"
    # makes every uploaded artifact executable by inference.
    assert _settings().ARTIFACT_TRUST_POLICY == "allowlist"


def test_invalid_pool_size_fails() -> None:
    with pytest.raises(ValidationError):
        _ = _settings(DB_POOL_SIZE=0)


def test_tracing_is_disabled_by_default() -> None:
    # Tracing must be opt-in: a default-on provider exports telemetry to an
    # external collector without the operator asking for it.
    assert _settings().OTEL_ENABLED is False


@pytest.mark.parametrize("value", [0.0, -0.1, 1.0001, 2.0])
def test_trace_sampler_arg_must_be_in_open_zero_one_interval(value: float) -> None:
    with pytest.raises(ValidationError):
        _ = _settings(OTEL_TRACES_SAMPLER_ARG=value)


def test_missing_database_url_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        _ = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
