"""BYODB onboarding request and public response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator

from .core.db_router import validate_database_url


class TenantDatabasePayload(BaseModel):
    """Private database URL supplied by a broker administrator."""

    database_url: SecretStr = Field(min_length=20, max_length=2048)

    @field_validator("database_url")
    @classmethod
    def validate_url(cls, value: SecretStr) -> SecretStr:
        validate_database_url(value.get_secret_value())
        return value


class TenantDatabaseResponse(BaseModel):
    tenant_id: UUID
    configured: bool
    migrated: bool
