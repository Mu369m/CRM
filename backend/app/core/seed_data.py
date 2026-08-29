"""Seed data initialization for new tenants."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DynamicRole,
    DynamicPermission,
    RolePermission,
    Pipeline,
    PipelineStage,
    CustomFieldGroup,
    CustomFieldDefinition,
)


class SeedDataInitializer:
    """Initialize default configuration for new tenants."""
    
    # Standard permissions
    STANDARD_PERMISSIONS = {
        # Lead permissions
        "leads.view": "View leads",
        "leads.create": "Create leads",
        "leads.edit": "Edit leads",
        "leads.delete": "Delete leads",
        "leads.export": "Export leads",
        
        # Client permissions
        "clients.view": "View clients",
        "clients.create": "Create clients",
        "clients.edit": "Edit clients",
        "clients.delete": "Delete clients",
        "clients.export": "Export clients",
        
        # Deposit permissions
        "deposits.view": "View deposits",
        "deposits.create": "Create deposits",
        "deposits.approve": "Approve deposits",
        "deposits.reject": "Reject deposits",
        "deposits.export": "Export deposits",
        
        # Withdrawal permissions
        "withdrawals.view": "View withdrawals",
        "withdrawals.create": "Create withdrawals",
        "withdrawals.approve": "Approve withdrawals",
        "withdrawals.reject": "Reject withdrawals",
        "withdrawals.export": "Export withdrawals",
        
        # KYC permissions
        "kyc.view": "View KYC documents",
        "kyc.create": "Create KYC documents",
        "kyc.approve": "Approve KYC",
        "kyc.reject": "Reject KYC",
        
        # IB permissions
        "ib.view": "View IBs",
        "ib.create": "Create IBs",
        "ib.edit": "Edit IBs",
        "ib.delete": "Delete IBs",
        
        # Report permissions
        "reports.view": "View reports",
        "reports.create": "Create reports",
        
        # Settings permissions
        "settings.manage": "Manage settings",
        "users.manage": "Manage users",
    }
    
    # Default roles
    DEFAULT_ROLES = {
        "SUPER_ADMIN": {
            "description": "Full access to all features",
            "permissions": list(STANDARD_PERMISSIONS.keys()),
        },
        "BROKER_ADMIN": {
            "description": "Broker administration",
            "permissions": list(STANDARD_PERMISSIONS.keys()),
        },
        "MANAGER": {
            "description": "Team and lead management",
            "permissions": [
                "leads.view", "leads.create", "leads.edit", "leads.delete", "leads.export",
                "clients.view", "clients.create", "clients.edit",
                "users.manage",
                "reports.view",
            ],
        },
        "SALES": {
            "description": "Sales operations",
            "permissions": [
                "leads.view", "leads.create", "leads.edit", "leads.export",
                "clients.view", "clients.create", "clients.edit",
                "deposits.view", "deposits.create",
                "reports.view",
            ],
        },
        "COMPLIANCE": {
            "description": "Compliance and KYC",
            "permissions": [
                "kyc.view", "kyc.approve", "kyc.reject",
                "clients.view",
                "deposits.view", "deposits.approve", "deposits.reject",
                "withdrawals.view", "withdrawals.approve", "withdrawals.reject",
                "reports.view",
            ],
        },
        "FINANCE": {
            "description": "Financial operations",
            "permissions": [
                "deposits.view", "deposits.approve", "deposits.reject", "deposits.export",
                "withdrawals.view", "withdrawals.approve", "withdrawals.reject", "withdrawals.export",
                "clients.view",
                "reports.view",
            ],
        },
        "IB_MANAGER": {
            "description": "IB partner management",
            "permissions": [
                "ib.view", "ib.create", "ib.edit",
                "clients.view",
                "reports.view",
            ],
        },
    }
    
    @staticmethod
    async def initialize_tenant(db: AsyncSession, tenant_id: UUID) -> None:
        """
        Initialize default seed data for a new tenant.
        
        Creates:
        - Default roles
        - Standard permissions
        - Default pipeline
        """
        # Check if already initialized
        existing = await db.scalar(
            select(DynamicRole).where(
                DynamicRole.tenant_id == tenant_id,
                DynamicRole.name == "SUPER_ADMIN"
            )
        )
        if existing:
            return  # Already initialized
        
        # Create permissions
        permissions_map: dict[str, DynamicPermission] = {}
        for perm_code, perm_desc in SeedDataInitializer.STANDARD_PERMISSIONS.items():
            perm = DynamicPermission(
                tenant_id=tenant_id,
                code=perm_code,
                description=perm_desc,
                module=perm_code.split(".")[0].upper(),
                action=perm_code.split(".")[1].upper(),
            )
            db.add(perm)
            await db.flush()
            permissions_map[perm_code] = perm
        
        # Create roles
        for role_name, role_config in SeedDataInitializer.DEFAULT_ROLES.items():
            role = DynamicRole(
                tenant_id=tenant_id,
                name=role_name,
                description=role_config["description"],
                is_system=True,
            )
            db.add(role)
            await db.flush()
            
            # Assign permissions to role
            for perm_code in role_config["permissions"]:
                perm = permissions_map[perm_code]
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(role_perm)
        
        # Create default lead pipeline
        lead_pipeline = Pipeline(
            tenant_id=tenant_id,
            name="Standard Lead Pipeline",
            entity_type="LEAD",
            description="Default lead pipeline",
            is_default=True,
        )
        db.add(lead_pipeline)
        await db.flush()
        
        # Create pipeline stages
        stages_data = [
            ("New Lead", "#3B82F6", 0, False),
            ("Contacted", "#8B5CF6", 1, False),
            ("Interested", "#EC4899", 2, False),
            ("Qualified", "#F59E0B", 3, False),
            ("Proposal", "#10B981", 4, False),
            ("Negotiation", "#06B6D4", 5, False),
            ("Won", "#34D399", 6, True),
            ("Lost", "#EF4444", 7, True),
        ]
        
        for stage_name, color, order, is_terminal in stages_data:
            stage = PipelineStage(
                pipeline_id=lead_pipeline.id,
                name=stage_name,
                color=color,
                display_order=order,
                is_terminal=is_terminal,
            )
            db.add(stage)
        
        # Create default client pipeline
        client_pipeline = Pipeline(
            tenant_id=tenant_id,
            name="Standard Client Pipeline",
            entity_type="CLIENT",
            description="Default client lifecycle",
            is_default=True,
        )
        db.add(client_pipeline)
        await db.flush()
        
        # Create client pipeline stages
        client_stages = [
            ("Prospect", "#3B82F6", 0, False),
            ("KYC Pending", "#F59E0B", 1, False),
            ("KYC Approved", "#10B981", 2, False),
            ("Account Active", "#34D399", 3, False),
            ("Trading", "#EC4899", 4, False),
            ("Inactive", "#6B7280", 5, True),
            ("Closed", "#EF4444", 6, True),
        ]
        
        for stage_name, color, order, is_terminal in client_stages:
            stage = PipelineStage(
                pipeline_id=client_pipeline.id,
                name=stage_name,
                color=color,
                display_order=order,
                is_terminal=is_terminal,
            )
            db.add(stage)
        
        await db.commit()
