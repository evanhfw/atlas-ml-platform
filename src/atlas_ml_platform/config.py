from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Atlas ML Platform"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    DB_POOL_SIZE: int = Field(default=5, gt=0)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0)
    DB_POOL_TIMEOUT: float = Field(default=30.0, gt=0)
    DB_POOL_RECYCLE: int = Field(default=1800, gt=0)

    S3_ENDPOINT: str = "localhost:8333"
    S3_ACCESS_KEY: str = "atlas"
    S3_SECRET_KEY: str = "atlas_s3_password"
    S3_BUCKET: str = "atlas-models"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False
    S3_CONNECT_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
    S3_READ_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    S3_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)

    READINESS_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
    SHUTDOWN_GRACE_SECONDS: float = Field(default=20.0, gt=0)

    ARTIFACT_MAX_SIZE_BYTES: int = Field(default=100 * 1024 * 1024, gt=0)

    # Empty by default: joblib/pickle deserialization is code execution.
    # Only checksums explicitly listed here may be loaded by the inference runtime.
    TRUSTED_ARTIFACT_CHECKSUMS: str = ""
    # "allowlist" is production-safe. "auto" trusts every uploaded artifact;
    # it is for local development only and is rejected in production.
    ARTIFACT_TRUST_POLICY: Literal["allowlist", "auto"] = "allowlist"
    MODEL_CACHE_MAX_ENTRIES: int = Field(default=8, gt=0)
    MODEL_LOAD_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    INFERENCE_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    INFERENCE_MAX_BATCH_SIZE: int = Field(default=256, gt=0)

    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "atlas-ml-platform"
    OTEL_SERVICE_VERSION: str = "0.1.0"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://127.0.0.1:4318"
    OTEL_TRACES_SAMPLER_ARG: float = Field(default=1.0, gt=0.0, le=1.0)

    @field_validator("TRUSTED_ARTIFACT_CHECKSUMS")
    @classmethod
    def _validate_trusted_checksums(cls, value: str) -> str:
        for raw in value.split(","):
            checksum = raw.strip().lower()
            if not checksum:
                continue
            if len(checksum) != 64 or any(
                char not in "0123456789abcdef" for char in checksum
            ):
                raise ValueError("Trusted artifact checksums must be SHA-256 hex")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Unsupported LOG_LEVEL: {value}")
        return level

    @property
    def trusted_artifact_checksums(self) -> frozenset[str]:
        return frozenset(
            checksum.strip().lower()
            for checksum in self.TRUSTED_ARTIFACT_CHECKSUMS.split(",")
            if checksum.strip()
        )

    @model_validator(mode="after")
    def _validate_artifact_trust_policy(self) -> Self:
        if self.APP_ENV == "production" and self.ARTIFACT_TRUST_POLICY == "auto":
            raise ValueError("ARTIFACT_TRUST_POLICY=auto is not allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
