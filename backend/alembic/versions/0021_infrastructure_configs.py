"""Add independent tenant database and storage configuration."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_infrastructure_configs"
down_revision = "0020_integration_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "infrastructure_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="SAAS"),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("engine", sa.String(length=40), nullable=True),
        sa.Column(
            "config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="NOT_CONFIGURED",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "kind", name="uq_infrastructure_tenant_kind"),
    )
    op.create_index(
        "ix_infrastructure_configs_tenant_id", "infrastructure_configs", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_infrastructure_configs_tenant_id", table_name="infrastructure_configs"
    )
    op.drop_table("infrastructure_configs")
