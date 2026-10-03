"""Application settings, loaded from environment variables (see .env.example)."""
from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"


def normalize_database_url(url: str) -> str:
    """Accept the URL exactly as hosted Postgres providers (Neon, Supabase, Render) hand it out.

    - postgres:// and postgresql:// become postgresql+asyncpg:// (the async driver we ship)
    - libpq's sslmode=... becomes asyncpg's ssl=...; libpq-only params (channel_binding) are dropped
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+asyncpg://"):
        return url
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "channel_binding":
            continue
        query.append(("ssl", value) if key == "sslmode" else (key, value))
    return urlunsplit(parts._replace(query=urlencode(query)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "production", "test"] = "development"
    public_demo_mode: bool = False
    secret_key: str = Field(default="dev-insecure-change-me")

    database_url: str = "sqlite+aiosqlite:///./lens-dev.sqlite"

    @field_validator("database_url")
    @classmethod
    def _normalize_db(cls, v: str) -> str:
        return normalize_database_url(v)

    model_provider: Literal["mock", "local", "ollama", "openai_compatible"] = "mock"
    model_name: str = "mock-deterministic-v1"
    device: Literal["auto", "cpu", "cuda"] = "auto"

    model_context_length: int = 4096
    ollama_base_url: str = "http://localhost:11434"
    openai_compat_base_url: str = ""
    openai_compat_api_key: SecretStr | None = None  # optional adapter only; never needed by the core app

    request_timeout_s: float = 60.0
    max_concurrency: int = 4
    max_retries: int = 2
    retry_backoff_s: float = 0.5
    max_runs_per_experiment: int = 500
    public_max_runs_per_experiment: int = 40

    frontend_dist: str = ""  # directory with the built SPA; when set, the API also serves the UI (single container)
    public_rate_limit_per_minute: int = 20  # write requests per client IP, enforced only in public demo mode
    public_max_total_experiments: int = 300  # protects the free database quota in public demo mode

    cors_origins: str = "http://localhost,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_max_runs(self) -> int:
        return self.public_max_runs_per_experiment if self.public_demo_mode else self.max_runs_per_experiment

    @property
    def is_mock(self) -> bool:
        return self.model_provider == "mock"

    def assert_production_safe(self) -> None:
        """Refuse to boot in production with the placeholder secret."""
        if self.app_env == "production" and self.secret_key.startswith(("dev-", "change-me")):
            raise RuntimeError("SECRET_KEY must be set to a strong random value in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
