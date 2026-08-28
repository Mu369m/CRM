"""Add finance transactions and tenant payment gateways."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_finance_and_payment_gateways"
down_revision = "0006_kyc_schema_and_account_provisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("payment_gateways", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("type", sa.String(20), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("config_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.UniqueConstraint("tenant_id", "name", name="uq_payment_gateway_tenant_name"))
    op.create_index("ix_payment_gateways_tenant_id", "payment_gateways", ["tenant_id"])
    op.create_table("transactions", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("trader_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("type", sa.String(30), nullable=False), sa.Column("amount", sa.Numeric(20, 8), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"), sa.Column("gateway_id", uuid, sa.ForeignKey("payment_gateways.id", ondelete="SET NULL")), sa.Column("payment_proof_url", sa.Text()), sa.Column("rejection_note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_transactions_tenant_id", "transactions", ["tenant_id"])
    op.create_index("ix_transactions_trader_id", "transactions", ["trader_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_trader_id", table_name="transactions")
    op.drop_index("ix_transactions_tenant_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_payment_gateways_tenant_id", table_name="payment_gateways")
    op.drop_table("payment_gateways")