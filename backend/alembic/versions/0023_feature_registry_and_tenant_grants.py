"""Add reusable feature registry and tenant-specific grants."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023_feature_registry_and_tenant_grants"
down_revision = "0022_owner_plan_and_impersonation_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "feature_definitions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("feature_key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column(
            "feature_type", sa.String(40), nullable=False, server_default="MODULE"
        ),
        sa.Column("version", sa.String(30), nullable=False, server_default="1.0"),
        sa.Column(
            "is_available", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "eligible_plans", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "pricing_type", sa.String(30), nullable=False, server_default="INCLUDED"
        ),
        sa.Column(
            "configuration_schema",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("feature_key", name="uq_feature_definition_key"),
    )
    op.create_index(
        "ix_feature_definitions_feature_key", "feature_definitions", ["feature_key"]
    )
    op.create_index(
        "ix_feature_definitions_is_available", "feature_definitions", ["is_available"]
    )
    op.create_table(
        "tenant_feature_grants",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "tenant_id",
            uuid,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            uuid,
            sa.ForeignKey("feature_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="DISABLED"),
        sa.Column(
            "configuration", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "feature_id", name="uq_tenant_feature_grant"),
    )
    op.create_index(
        "ix_tenant_feature_grants_tenant_id", "tenant_feature_grants", ["tenant_id"]
    )
    op.create_index(
        "ix_tenant_feature_grants_feature_id", "tenant_feature_grants", ["feature_id"]
    )
    op.create_index(
        "ix_tenant_feature_grants_status", "tenant_feature_grants", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_feature_grants_status", table_name="tenant_feature_grants")
    op.drop_index(
        "ix_tenant_feature_grants_feature_id", table_name="tenant_feature_grants"
    )
    op.drop_index(
        "ix_tenant_feature_grants_tenant_id", table_name="tenant_feature_grants"
    )
    op.drop_table("tenant_feature_grants")
    op.drop_index(
        "ix_feature_definitions_is_available", table_name="feature_definitions"
    )
    op.drop_index(
        "ix_feature_definitions_feature_key", table_name="feature_definitions"
    )
    op.drop_table("feature_definitions")
