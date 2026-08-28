"""Runtime tenant configuration contracts."""

from pydantic import BaseModel, ConfigDict, Field


class TenantSettingsPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = Field(default=None, max_length=500)
    favicon_url: str | None = Field(default=None, max_length=500)
    meta_title: str = Field(min_length=1, max_length=160)
    support_email: str | None = None
    max_ib_levels: int = Field(ge=1, le=100)
    tenant_schema: str = Field(pattern=r"^tenant_[0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{12}$")
