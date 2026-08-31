"""Add tenant payment methods and master controls."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_payment_methods"
down_revision = "0010_trader_profile_kyc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("tenant_payment_methods", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("method", sa.String(30), nullable=False), sa.Column("network", sa.String(30), nullable=False), sa.Column("asset", sa.String(12), nullable=False), sa.Column("chain_id", sa.String(80)), sa.Column("contract_address", sa.String(120)), sa.Column("deposit_address", sa.String(200)), sa.Column("qr_code_url", sa.Text), sa.Column("account_details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("min_deposit", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("max_deposit", sa.Numeric(20, 8)), sa.Column("min_withdrawal", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("processing_fee", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("is_active_broker", sa.Boolean, nullable=False, server_default=sa.false()), sa.UniqueConstraint("tenant_id", "method", "network", "asset", name="uq_tenant_payment_method"))
    op.create_index("ix_tenant_payment_methods_tenant_id", "tenant_payment_methods", ["tenant_id"])
    op.create_table("master_payment_controls", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid), sa.Column("method", sa.String(30), nullable=False), sa.Column("network", sa.String(30), nullable=False), sa.Column("asset", sa.String(12), nullable=False), sa.Column("is_active_master", sa.Boolean, nullable=False, server_default=sa.true()))
    op.create_index("ix_master_payment_controls_tenant_id", "master_payment_controls", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_master_payment_controls_tenant_id", table_name="master_payment_controls")
    op.drop_table("master_payment_controls")
    op.drop_index("ix_tenant_payment_methods_tenant_id", table_name="tenant_payment_methods")
    op.drop_table("tenant_payment_methods")