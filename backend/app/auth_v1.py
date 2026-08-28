"""Tenant-scoped registration and login API."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import IbPartner, Role, Tenant, User
from .security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    parent_ib_id: UUID | None = None
    full_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


async def get_current_tenant(
    x_tenant_id: str | None = Header(default=None),
    x_tenant_host: str | None = Header(default=None, alias="X-Tenant-Host"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resolve an active tenant from its verified host or UUID header."""
    host = (x_tenant_host or "").split(":", 1)[0].lower()
    tenant = None
    if host:
        tenant = await db.scalar(select(Tenant).where(Tenant.is_active.is_(True), (Tenant.subdomain == host) | (Tenant.custom_domain == host)))
    if not tenant and x_tenant_id:
        try:
            tenant_id = UUID(x_tenant_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Tenant identity must be a valid UUID") from error
        tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True)))
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant host or identity is required")
    return tenant


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterSchema, ref: str | None = Query(default=None, max_length=50), tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    """Register a trader inside one tenant and hash the password with Argon2id."""
    existing = await db.scalar(select(User).where(User.email == data.email.lower(), User.tenant_id == tenant.id))
    if existing:
        raise HTTPException(status_code=409, detail="User already exists for this broker")
    if data.parent_ib_id:
        parent = await db.scalar(select(User).where(User.id == data.parent_ib_id, User.tenant_id == tenant.id, User.role == Role.IB_PARTNER))
        if not parent:
            raise HTTPException(status_code=400, detail="Parent IB is invalid for this tenant")
    parent_ib_id = data.parent_ib_id
    if ref:
        partner = await db.scalar(select(IbPartner).where(IbPartner.tenant_id == tenant.id, IbPartner.referral_code == ref))
        if not partner:
            raise HTTPException(status_code=400, detail="Referral code is invalid")
        parent_ib_id = partner.user_id
    user = User(tenant_id=tenant.id, email=data.email.lower(), full_name=data.full_name, phone=data.phone, country=data.country, password_hash=hash_password(data.password), role=Role.TRADER, parent_ib_id=parent_ib_id)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"message": "User registered successfully", "user_id": str(user.id)}


@router.post("/login")
async def login(data: LoginSchema, tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    """Authenticate against the requested tenant and issue a short-lived JWT."""
    user = await db.scalar(select(User).where(User.email == data.email.lower(), User.tenant_id == tenant.id))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id, tenant.id, user.role)
    return {"access_token": token, "token_type": "bearer"}
