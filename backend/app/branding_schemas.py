"""Public tenant branding response contract."""

from pydantic import BaseModel, ConfigDict


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
