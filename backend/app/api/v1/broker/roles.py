"""
Role and permission management API endpoints.

Allows brokers to create custom roles and manage permissions.
"""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db import get_tenant_db
from app.security import current_claims
from app.models import (
    DynamicRole,
    DynamicPermission,
    RolePermission,
    UserDynamicRole,
)
from app.middleware.permission_check import check_permission, STANDARD_PERMISSIONS

router = APIRouter(prefix="/roles", tags=["roles"])


# ========== Schemas ==========

class CreateRole(BaseModel):
    name: str
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sales Manager",
                "description": "Can manage sales team and leads"
            }
        }


class UpdateRole(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DynamicRoleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    is_system: bool
    permission_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    description: Optional[str]
    module: str
    action: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoleDetailResponse(DynamicRoleResponse):
    permissions: List[PermissionResponse]


# ========== Endpoints ==========

@router.post("/", response_model=DynamicRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: CreateRole,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create custom role. Requires: settings.manage"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    role = DynamicRole(
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        is_system=False,
    )
    
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return role


@router.get("/", response_model=List[DynamicRoleResponse])
async def list_roles(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all roles for tenant"""
    
    tenant_id = UUID(claims["tenant_id"])

    if not await check_permission(UUID(claims["sub"]), "settings", "manage", db, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(DynamicRole).where(DynamicRole.tenant_id == tenant_id)
    )
    return result.scalars().all()


@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role(
    role_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get role with permissions"""
    
    tenant_id = UUID(claims["tenant_id"])

    if not await check_permission(UUID(claims["sub"]), "settings", "manage", db, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(DynamicRole).where(
            (DynamicRole.id == role_id) & (DynamicRole.tenant_id == tenant_id)
        )
    )
    role = result.scalar()
    
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Get permissions for this role
    result = await db.execute(
        select(DynamicPermission)
        .join(RolePermission)
        .where(RolePermission.role_id == role_id)
        .where(DynamicPermission.tenant_id == tenant_id)
    )
    permissions = result.scalars().all()
    
    response = RoleDetailResponse(
        **{**role.__dict__, "permissions": permissions}
    )
    return response


@router.put("/{role_id}", response_model=DynamicRoleResponse)
async def update_role(
    role_id: UUID,
    payload: UpdateRole,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update role"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(DynamicRole).where(
            (DynamicRole.id == role_id) & (DynamicRole.tenant_id == tenant_id)
        )
    )
    role = result.scalar()
    
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Cannot edit default roles
    if role.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify default roles"
        )
    
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(role, key, value)
    
    await db.commit()
    await db.refresh(role)
    
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete role (cannot delete default roles)"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(DynamicRole).where(
            (DynamicRole.id == role_id) & (DynamicRole.tenant_id == tenant_id)
        )
    )
    role = result.scalar()
    
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete default roles"
        )
    
    await db.delete(role)
    await db.commit()


# ========== Permissions ==========

@router.get("/available/permissions", response_model=List[PermissionResponse])
async def get_available_permissions(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all available permissions"""
    
    tenant_id = UUID(claims["tenant_id"])

    if not await check_permission(UUID(claims["sub"]), "settings", "manage", db, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(DynamicPermission).where(DynamicPermission.tenant_id == tenant_id)
    )
    return result.scalars().all()


@router.post("/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_permission(
    role_id: UUID,
    permission_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Grant permission to role"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Verify role exists
    result = await db.execute(
        select(DynamicRole).where(
            (DynamicRole.id == role_id) & (DynamicRole.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    # Verify permission exists
    result = await db.execute(
        select(DynamicPermission).where(
            (DynamicPermission.id == permission_id)
            & (DynamicPermission.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        )
    
    # Check if already granted
    result = await db.execute(
        select(RolePermission).where(
            (RolePermission.role_id == role_id)
            & (RolePermission.permission_id == permission_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission already granted"
        )
    
    # Grant permission
    role_perm = RolePermission(
        role_id=role_id,
        permission_id=permission_id,
    )
    db.add(role_perm)
    await db.commit()


@router.delete("/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    role_id: UUID,
    permission_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Revoke permission from role"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(RolePermission).where(
            (RolePermission.role_id == role_id)
            & (RolePermission.permission_id == permission_id)
        )
    )
    role_perm = result.scalar()
    
    if not role_perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    await db.delete(role_perm)
    await db.commit()
