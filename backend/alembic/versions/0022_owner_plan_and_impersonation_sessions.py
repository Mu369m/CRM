"""Persist broker plans and view-as-broker session state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_owner_plan_and_impersonation_sessions"
down_revision = "0021_infrastructure_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column(
        "tenants",
        sa.Column("plan", sa.String(30), nullable=False, server_default="STARTER"),
    )
    op.create_index("ix_tenants_plan", "tenants", ["plan"])
    op.create_table(
        "view_as_broker_sessions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "admin_id",
            uuid,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            uuid,
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_view_as_broker_sessions_admin_id", "view_as_broker_sessions", ["admin_id"]
    )
    op.create_index(
        "ix_view_as_broker_sessions_tenant_id", "view_as_broker_sessions", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_view_as_broker_sessions_tenant_id", table_name="view_as_broker_sessions"
    )
    op.drop_index(
        "ix_view_as_broker_sessions_admin_id", table_name="view_as_broker_sessions"
    )
    op.drop_table("view_as_broker_sessions")
    op.drop_index("ix_tenants_plan", table_name="tenants")
    op.drop_column("tenants", "plan")
