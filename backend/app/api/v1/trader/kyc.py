"""Trader KYC submission and document status APIs."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config import get_settings
from ....core.db_router import get_tenant_db
from ....models import KycDocument, KycStatus, Role, TenantSettings, User
from ....security import require_roles

router = APIRouter(prefix="/api/v1/trader/kyc", tags=["Trader KYC"])
TraderClaims = Annotated[dict[str, str], Depends(require_roles(Role.TRADER, Role.IB_PARTNER))]


class UploadRequest(BaseModel):
    document_type: str = Field(min_length=3, max_length=50)
    content_type: str = Field(pattern=r"^(image/(jpeg|png)|application/pdf)$")


class KycSubmissionPayload(BaseModel):
    document_type: str = Field(min_length=3, max_length=50)
    storage_key: str = Field(min_length=1, max_length=500)
    fields: dict[str, str] = Field(default_factory=dict, max_length=100)


@router.post("/upload-url")
async def upload_url(payload: UploadRequest, claims: TraderClaims):
    base_url = getattr(get_settings(), "kyc_upload_base_url", None)
    if not base_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="KYC object storage is not configured")
    token = secrets.token_urlsafe(32)
    key = f"kyc/{claims['tenant_id']}/{claims['sub']}/{token}-{payload.document_type}"
    return {"upload_url": f"{base_url.rstrip('/')}/{key}", "storage_key": key, "expires_at": datetime.now(UTC) + timedelta(minutes=10), "method": "PUT", "content_type": payload.content_type}


@router.post("/submit")
async def submit_kyc(payload: KycSubmissionPayload, claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db)):
    tenant_id = UUID(claims["tenant_id"])
    configured = await db.get(TenantSettings, tenant_id)
    schema = configured.kyc_schema if configured else {}
    allowed = {field.get("key") for field in schema.get("custom_fields", []) if isinstance(field, dict)}
    if allowed and not set(payload.fields).issubset(allowed):
        raise HTTPException(status_code=422, detail="Submitted KYC fields do not match the tenant schema")
    document = KycDocument(tenant_id=tenant_id, user_id=UUID(claims["sub"]), document_type=payload.document_type, storage_key=payload.storage_key, submission_data=payload.fields, status=KycStatus.PENDING)
    db.add(document)
    user = await db.scalar(select(User).where(User.id == UUID(claims["sub"]), User.tenant_id == tenant_id).with_for_update())
    user.kyc_status = KycStatus.PENDING
    user.is_kyc_verified = False
    await db.commit()
    await db.refresh(document)
    return {"id": document.id, "document_type": document.document_type, "status": document.status, "created_at": document.created_at}


@router.get("/documents")
async def documents(claims: TraderClaims, db: AsyncSession = Depends(get_tenant_db)):
    items = await db.scalars(select(KycDocument).where(KycDocument.user_id == UUID(claims["sub"]), KycDocument.tenant_id == UUID(claims["tenant_id"])).order_by(KycDocument.created_at.desc()))
    return list(items)
