"""Validated application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; secrets must be injected by the deployment platform."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Brokerage CRM API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://crm:crm@localhost:5432/brokerage_crm"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    field_encryption_key: SecretStr
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Build settings once per process so every dependency shares one snapshot."""
    return Settings()
