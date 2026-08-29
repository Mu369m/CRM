"""
Permission checking middleware and utilities.

Enforces RBAC on all broker endpoints.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DynamicRole,
    DynamicPermission,
    RolePermission,
    UserDynamicRole,
)


async def check_permission(
    user_id: UUID,
    resource: str,
    action: str,
    db: AsyncSession,
    tenant_id: UUID,
) -> bool:
    """
    Check if user has permission for resource action.
    
    Args:
        user_id: User ID
        resource: Resource name (leads, clients, deposits, etc.)
        action: Action name (view, create, edit, delete, approve, reject)
        db: Database session
        tenant_id: Tenant ID
        
    Returns:
        True if user has permission, False otherwise
        
    Examples:
        check_permission(user_id, "leads", "create", db, tenant_id)
        check_permission(user_id, "deposits", "approve", db, tenant_id)
    """
    
    # Get all roles for user
    result = await db.execute(
        select(UserDynamicRole).where(
            (UserDynamicRole.user_id == user_id)
            & (UserDynamicRole.tenant_id == tenant_id)
        )
    )
    user_roles = result.scalars().all()
    
    if not user_roles:
        return False
    
    role_ids = [ur.role_id for ur in user_roles]
    
    # Build permission string
    permission_name = f"{resource}.{action}"
    
    # Check if any of user's roles have this permission
    result = await db.execute(
        select(RolePermission)
        .join(DynamicPermission)
        .where(
            (RolePermission.role_id.in_(role_ids))
            & (DynamicPermission.name == permission_name)
            & (DynamicPermission.tenant_id == tenant_id)
        )
    )
    
    return result.scalar() is not None


async def get_user_permissions(
    user_id: UUID,
    db: AsyncSession,
    tenant_id: UUID,
) -> set[str]:
    """
    Get all permissions for a user.
    
    Returns:
        Set of permission names like {'leads.view', 'leads.create', ...}
    """
    
    # Get user's roles
    result = await db.execute(
        select(UserDynamicRole).where(
            (UserDynamicRole.user_id == user_id)
            & (UserDynamicRole.tenant_id == tenant_id)
        )
    )
    user_roles = result.scalars().all()
    
    if not user_roles:
        return set()
    
    role_ids = [ur.role_id for ur in user_roles]
    
    # Get all permissions for these roles
    result = await db.execute(
        select(DynamicPermission)
        .join(RolePermission)
        .where(
            (RolePermission.role_id.in_(role_ids))
            & (DynamicPermission.tenant_id == tenant_id)
        )
    )
    
    permissions = result.scalars().all()
    return {p.name for p in permissions}


# Standard permission names
STANDARD_PERMISSIONS = [
    # Lead permissions
    "leads.view",
    "leads.create",
    "leads.edit",
    "leads.delete",
    "leads.export",
    
    # Client permissions
    "clients.view",
    "clients.create",
    "clients.edit",
    "clients.delete",
    "clients.export",
    
    # Deposit permissions
    "deposits.view",
    "deposits.create",
    "deposits.approve",
    "deposits.reject",
    "deposits.export",
    
    # Withdrawal permissions
    "withdrawals.view",
    "withdrawals.create",
    "withdrawals.approve",
    "withdrawals.reject",
    "withdrawals.export",
    
    # KYC permissions
    "kyc.view",
    "kyc.approve",
    "kyc.reject",
    
    # IB permissions
    "ib.view",
    "ib.create",
    "ib.edit",
    "ib.delete",
    
    # Report permissions
    "reports.view",
    "reports.create",
    
    # Settings permissions
    "settings.manage",
    "users.manage",
]
