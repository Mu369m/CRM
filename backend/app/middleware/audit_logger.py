"""Audit logging system for tracking all state changes."""

from datetime import datetime
from typing import Any
from uuid import UUID
import json

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditLogger:
    """Helper for logging audit events."""
    
    @staticmethod
    async def log(
        db: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        old_value: Any = None,
        new_value: Any = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Log an audit event.
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            actor_id: User performing the action
            action: Action type (CREATE, UPDATE, DELETE, APPROVE, REJECT, etc.)
            entity_type: Type of entity (LEAD, CLIENT, DEPOSIT, etc.)
            entity_id: ID of the entity
            old_value: Previous value (for updates)
            new_value: New value (for updates)
            metadata: Additional metadata
        """
        audit_metadata = metadata or {}
        audit_metadata.update({
            "entity_type": entity_type,
            "entity_id": str(entity_id),
        })
        
        if old_value is not None:
            audit_metadata["old_value"] = str(old_value)
        if new_value is not None:
            audit_metadata["new_value"] = str(new_value)
        
        audit_log = AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=f"{entity_type}:{action}",
            metadata_json=json.dumps(audit_metadata),
        )
        
        db.add(audit_log)
        await db.flush()
    
    @staticmethod
    async def log_create(
        db: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        data: dict,
    ) -> None:
        """Log entity creation."""
        await AuditLogger.log(
            db, tenant_id, actor_id, "CREATE", entity_type, entity_id,
            new_value=data
        )
    
    @staticmethod
    async def log_update(
        db: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        changes: dict,
    ) -> None:
        """Log entity update with changed fields."""
        await AuditLogger.log(
            db, tenant_id, actor_id, "UPDATE", entity_type, entity_id,
            metadata={"changes": changes}
        )
    
    @staticmethod
    async def log_delete(
        db: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        """Log entity deletion."""
        await AuditLogger.log(
            db, tenant_id, actor_id, "DELETE", entity_type, entity_id
        )
    
    @staticmethod
    async def log_approval(
        db: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        approval_type: str = "APPROVE",
        reason: str | None = None,
    ) -> None:
        """Log approval/rejection."""
        metadata = {"approval_type": approval_type}
        if reason:
            metadata["reason"] = reason
        
        await AuditLogger.log(
            db, tenant_id, actor_id, approval_type, entity_type, entity_id,
            metadata=metadata
        )
