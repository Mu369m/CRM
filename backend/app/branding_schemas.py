"""Public tenant branding response contract."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TenantBrandingResponse(BaseModel):
    """Safe public fields used to skin the tenant application shell."""

    model_config = ConfigDict(from_attributes=True)

    company_name: str
    primary_color: str
    secondary_color: str
    logo_url: str | None = None
    favicon_url: str | None = None
    meta_title: str
    support_email: str | None = None


class ThemeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["light", "dark", "system"] = "system"
    primary_color: str = Field(default="#0F172A", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = None
    favicon_url: str | None = None
    company_name: str = Field(default="Brokerage CRM", max_length=160)
    preset: Literal["modern", "professional", "minimal", "classic", "custom"] = (
        "professional"
    )
    custom_css: str | None = Field(default=None, max_length=50000)


class ThemeVersionResponse(BaseModel):
    id: str
    version: int
    status: Literal["DRAFT", "PUBLISHED"]
    config: dict[str, Any]
    created_at: str
    published_at: str | None = None


class ThemeDraftResponse(BaseModel):
    draft: ThemeVersionResponse | None = None
    published: ThemeVersionResponse | None = None


class ThemeDraftPayload(BaseModel):
    config: ThemeConfig
