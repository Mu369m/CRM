"""Tenant-scoped registration and login API."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import Role, Tenant, User
from .security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    parent_ib_id: UUID | None = None


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


async def get_current_tenant(
    x_tenant_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resolve an active tenant from a UUID header without accepting arbitrary identifiers."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header missing")
    try:
        tenant_id = UUID(x_tenant_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="X-Tenant-ID must be a valid UUID") from error
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True)))
    if not tenant:
        raise HTTPException(status_code=403, detail="Tenant invalid or inactive")
    return tenant


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterSchema, tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    """Register a trader inside one tenant and hash the password with Argon2id."""
    existing = await db.scalar(select(User).where(User.email == data.email.lower(), User.tenant_id == tenant.id))
    if existing:
        raise HTTPException(status_code=409, detail="User already exists for this broker")
    if data.parent_ib_id:
        parent = await db.scalar(select(User).where(User.id == data.parent_ib_id, User.tenant_id == tenant.id, User.role == Role.IB_PARTNER))
        if not parent:
            raise HTTPException(status_code=400, detail="Parent IB is invalid for this tenant")
    user = User(tenant_id=tenant.id, email=data.email.lower(), password_hash=hash_password(data.password), role=Role.TRADER, parent_ib_id=data.parent_ib_id)
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
