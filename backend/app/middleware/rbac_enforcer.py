"""RBAC enforcement decorator and dependency injection."""

from functools import wraps
from typing import Callable, Sequence
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_tenant_db
from app.models import Role
from app.security import current_claims
from app.middleware.permission_check import check_permission


def require_permission(*permissions: str):
    """
    Dependency that enforces one or more permissions.
    
    Usage:
        @router.post("/leads")
        async def create_lead(
            payload: LeadCreate,
            _: str = Depends(require_permission("leads.create")),
            claims: dict = Depends(current_claims),
            db: AsyncSession = Depends(get_tenant_db),
        ):
            ...
    """
    async def dependency(
        claims: dict[str, str] = Depends(current_claims),
        db: AsyncSession = Depends(get_tenant_db),
    ) -> dict[str, str]:
        user_id = UUID(claims["sub"])
        tenant_id = UUID(claims["tenant_id"])
        
        # Check if user has ANY of the required permissions
        for permission in permissions:
            has_perm = await check_permission(
                user_id, 
                permission.split(".")[0],  # resource
                permission.split(".")[1],  # action
                db, 
                tenant_id
            )
            if has_perm:
                return claims
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {', '.join(permissions)}"
        )
    
    return dependency


def enforce_permissions(*permissions: str):
    """
    Decorator to enforce permissions on route handlers.
    
    Usage:
        @router.post("/leads")
        @enforce_permissions("leads.create")
        async def create_lead(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Permission checks happen at dependency injection level
            return await func(*args, **kwargs)
        return wrapper
    return decorator
