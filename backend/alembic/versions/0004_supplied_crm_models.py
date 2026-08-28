"""Add supplied tenant branding, domain, server, and IB rule fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_supplied_crm_models"
down_revision = "0003_runtime_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend shared entities and create the supplied configuration models."""
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column("tenants", sa.Column("subdomain", sa.String(50), unique=True))
    op.add_column("tenants", sa.Column("custom_domain", sa.String(160), unique=True))
    op.add_column("tenants", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("users", sa.Column("is_kyc_verified", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("users", sa.Column("parent_ib_id", uuid, sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_users_parent_ib_id", "users", ["parent_ib_id"])
    op.create_table("tenant_brandings", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("primary_color", sa.String(7), nullable=False), sa.Column("secondary_color", sa.String(7), nullable=False), sa.Column("logo_url", sa.Text()), sa.Column("favicon_url", sa.Text()))
    op.create_table("mt_server_configs", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("server_name", sa.String(100), nullable=False), sa.Column("platform_type", sa.String(20), nullable=False), sa.Column("manager_ip", sa.String(100), nullable=False), sa.Column("encrypted_credentials", sa.Text(), nullable=False))
    op.create_table("ib_rebate_rules", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("rule_name", sa.String(100), nullable=False), sa.Column("rebate_type", sa.String(40), nullable=False), sa.Column("tier_rates", postgresql.JSONB, nullable=False), sa.UniqueConstraint("tenant_id", "rule_name", name="uq_ib_rebate_rule_name"))


def downgrade() -> None:
    """Remove supplied model additions."""
    op.drop_table("ib_rebate_rules")
    op.drop_table("mt_server_configs")
    op.drop_table("tenant_brandings")
    op.drop_index("ix_users_parent_ib_id", table_name="users")
    op.drop_column("users", "parent_ib_id")
    op.drop_column("users", "is_kyc_verified")
    op.drop_column("tenants", "is_active")
    op.drop_column("tenants", "custom_domain")
    op.drop_column("tenants", "subdomain")
