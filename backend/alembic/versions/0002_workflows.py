"""Add identity hardening and client workflow tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_workflows"
down_revision = "0001_core_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 2FA state plus KYC, trading account, treasury, and IB records."""
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table("kyc_documents", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("document_type", sa.String(50), nullable=False), sa.Column("storage_key", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("review_note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_table("trading_accounts", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("platform", sa.String(20), nullable=False), sa.Column("external_login", sa.String(80), nullable=False), sa.Column("server", sa.String(160), nullable=False), sa.Column("is_demo", sa.Boolean(), nullable=False), sa.Column("leverage", sa.Integer(), nullable=False), sa.Column("is_locked", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("platform", "external_login", "server", name="uq_trading_account_external"))
    op.create_table("money_requests", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("kind", sa.String(20), nullable=False), sa.Column("amount", sa.Numeric(20, 8), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("provider_reference", sa.String(160)), sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_table("ib_partners", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("parent_id", uuid, sa.ForeignKey("ib_partners.id")), sa.Column("referral_code", sa.String(50), nullable=False, unique=True), sa.Column("commission_rate", sa.Numeric(12, 6), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    """Remove workflow tables and 2FA columns."""
    op.drop_table("ib_partners")
    op.drop_table("money_requests")
    op.drop_table("trading_accounts")
    op.drop_table("kyc_documents")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret_encrypted")
