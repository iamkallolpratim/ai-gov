"""Environment-driven application configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Values shipped in `.env.example` and docker-compose. Public by definition, so they
#: must never reach a deployed environment.
PUBLIC_DEFAULTS = frozenset(
    {
        "change-me-in-production",
        "local-dev-secret-change-me",
        "aigov",
        "minioadmin",
        "postgres",
        "changeme",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "AI Governance Console"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["local", "test", "staging", "production"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # --- Security ---
    #: Run the API without authentication. Every request is then attributed to a
    #: synthetic system account with the admin role. Only safe on a network where
    #: reaching the API already implies authorisation (private VPC, localhost).
    #: See the "Authentication modes" section of the README.
    AUTH_DISABLED: bool = False
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    #: Accepts a comma-separated list ("http://a,http://b") or a JSON array.
    #: `NoDecode` is essential: without it pydantic-settings tries `json.loads` on the
    #: raw environment value *before* any validator runs, so a plain comma-separated
    #: string raises SettingsError at import time.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Rate limits on sensitive or expensive endpoints ---
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_EVIDENCE: str = "20/hour"
    RATE_LIMIT_POLICY_CHECK: str = "60/hour"

    # --- Secure headers ---
    SECURITY_HEADERS_ENABLED: bool = True
    #: Sent only over HTTPS deployments; 0 disables the header.
    HSTS_MAX_AGE_SECONDS: int = 63072000

    # --- Database ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "aigov"
    POSTGRES_PASSWORD: str = "aigov"
    POSTGRES_DB: str = "aigov"
    DATABASE_URL: str | None = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- Redis / Celery ---
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"  # type: ignore[assignment]
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CACHE_TTL_SECONDS: int = 300
    #: An evidence package still pending/running after this long will never finish; it is
    #: marked failed and becomes retryable. Must stay above the worker's 600 s hard task
    #: time limit so a genuinely running job is never expired.
    EVIDENCE_STALE_AFTER_SECONDS: int = 900

    # --- OPA ---
    OPA_URL: str = "http://localhost:8181"
    OPA_TIMEOUT_SECONDS: float = 5.0
    OPA_POLICY_PACKAGE_ROOT: str = "aigov"
    #: Filesystem source of record for Rego. Docker mounts this straight into OPA;
    #: `POST /api/v1/policies/sync-opa` pushes it over the REST API instead.
    POLICY_DIR: str = "policies"
    #: Shared helper packages that carry no policy row of their own but must be
    #: loaded into OPA before any policy that imports them.
    #: Order matters: OPA will not compile a module that calls a function defined in one
    #: that has not been loaded yet, so the shared library comes first.
    POLICY_LIBRARY_FILES: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["common/aigov_common.rego", "eu/eu_ai_act_base.rego"]
    )

    # --- Object storage (S3-compatible) ---
    S3_ENDPOINT_URL: str | None = "http://localhost:9000"
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = "aigov-evidence"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_USE_SSL: bool = False
    S3_PRESIGN_EXPIRY_SECONDS: int = 3600

    # --- Rate limiting ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "120/minute"
    #: Defaults to REDIS_URL so limits are shared across workers. Use "memory://" for a
    #: single-process deployment or a test run.
    RATE_LIMIT_STORAGE_URI: str | None = None

    # --- Pagination ---
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 200

    @model_validator(mode="after")
    def _reject_default_secrets_outside_dev(self) -> Settings:
        """Fail fast rather than sign tokens with a publicly known key.

        This project is open source, so every default in `.env.example` is public.
        Booting staging or production with one of them would mean anyone could mint a
        valid admin token, so the app refuses to start instead.
        """
        if self.ENVIRONMENT not in ("staging", "production"):
            return self
        insecure = [
            name
            for name, value in (
                ("SECRET_KEY", self.SECRET_KEY),
                ("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD),
                ("S3_SECRET_ACCESS_KEY", self.S3_SECRET_ACCESS_KEY),
            )
            if value in PUBLIC_DEFAULTS
        ]
        if insecure:
            raise ValueError(
                f"Refusing to start in {self.ENVIRONMENT}: {', '.join(insecure)} still "
                "use the public example values. Set real secrets via the environment."
            )
        return self

    @property
    def refresh_token_expire_minutes(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60

    @property
    def rate_limit_storage_uri(self) -> str:
        return self.RATE_LIMIT_STORAGE_URI or str(self.REDIS_URL)

    @property
    def auth_enabled(self) -> bool:
        return not self.AUTH_DISABLED

    @field_validator("CORS_ORIGINS", "POLICY_LIBRARY_FILES", mode="before")
    @classmethod
    def _split_list(cls, v: object) -> object:
        """Parse a list setting from a comma-separated string or a JSON array.

        Environment variables are strings, and `FOO=a,b` is what people actually write
        in a .env file or a compose file, so both forms are accepted.
        """
        if not isinstance(v, str):
            return v
        text = v.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Value looks like JSON but does not parse: {text!r}") from exc
            if not isinstance(parsed, list):
                raise ValueError(f"Expected a JSON array, got {type(parsed).__name__}")
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in text.split(",") if item.strip()]

    @property
    def sqlalchemy_dsn(self) -> str:
        """Sync psycopg driver DSN used by the app and Alembic."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or str(self.REDIS_URL)

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or str(self.REDIS_URL)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
