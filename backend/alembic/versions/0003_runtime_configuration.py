"""Add runtime tenant configuration tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_runtime_configuration"
down_revision = "0002_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Persist tenant branding and business-rule configuration."""
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("tenant_settings", sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True), sa.Column("primary_color", sa.String(20), nullable=False), sa.Column("secondary_color", sa.String(20), nullable=False), sa.Column("logo_url", sa.Text()), sa.Column("favicon_url", sa.Text()), sa.Column("meta_title", sa.String(160), nullable=False), sa.Column("support_email", sa.String(320)), sa.Column("max_ib_levels", sa.Integer(), nullable=False), sa.Column("tenant_schema", sa.String(80), nullable=False, unique=True))
    op.create_table("rebate_rules", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("instrument_group", sa.String(80), nullable=False), sa.Column("strategy", sa.String(40), nullable=False), sa.Column("level", sa.Integer(), nullable=False), sa.Column("fixed_per_lot", sa.Numeric(20, 8), nullable=False), sa.Column("spread_percentage", sa.Numeric(12, 8), nullable=False), sa.Column("asset_class", sa.String(30)), sa.Column("enabled", sa.Boolean(), nullable=False), sa.UniqueConstraint("tenant_id", "instrument_group", "level", name="uq_rebate_rule_scope"))
    op.create_table("kyc_requirements", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("document_type", sa.String(50), nullable=False), sa.Column("required", sa.Boolean(), nullable=False), sa.Column("applies_to_country", sa.String(2)), sa.Column("enabled", sa.Boolean(), nullable=False), sa.UniqueConstraint("tenant_id", "document_type", name="uq_kyc_requirement_type"))
    op.create_table("bonus_rules", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("deposit_percentage", sa.Numeric(12, 8), nullable=False), sa.Column("max_credit", sa.Numeric(20, 8), nullable=False), sa.Column("withdrawal_lot_target", sa.Numeric(20, 8), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False))
    op.create_table("manager_connections", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("platform", sa.String(20), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("server", sa.String(160), nullable=False), sa.Column("login", sa.String(100), nullable=False), sa.Column("encrypted_password", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("tenant_id", "name", name="uq_manager_connection_name"))


def downgrade() -> None:
    """Remove runtime rule configuration tables."""
    op.drop_table("manager_connections")
    op.drop_table("bonus_rules")
    op.drop_table("kyc_requirements")
    op.drop_table("rebate_rules")
    op.drop_table("tenant_settings")
