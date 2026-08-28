"""Create tenant, identity, wallet, ledger, audit, and webhook tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_core_crm"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial transactional CRM persistence boundary."""
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("tenants", sa.Column("id", uuid, primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("users", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("email", sa.String(320), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(30), nullable=False), sa.Column("kyc_status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_table("wallets", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("owner_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("currency", sa.String(3), nullable=False), sa.Column("balance", sa.Numeric(20, 8), nullable=False), sa.CheckConstraint("balance >= 0", name="ck_wallet_balance_nonnegative"))
    op.create_table("ledger_entries", sa.Column("id", uuid, primary_key=True), sa.Column("wallet_id", uuid, sa.ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False), sa.Column("entry_type", sa.String(30), nullable=False), sa.Column("amount", sa.Numeric(20, 8), nullable=False), sa.Column("reference", sa.String(120), nullable=False, unique=True), sa.Column("note", sa.Text), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_ledger_entries_wallet_id", "ledger_entries", ["wallet_id"])
    op.create_table("audit_logs", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_id", uuid, nullable=False), sa.Column("action", sa.String(120), nullable=False), sa.Column("metadata_json", sa.Text, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_table("webhook_events", sa.Column("id", uuid, primary_key=True), sa.Column("tenant_id", uuid, nullable=True), sa.Column("provider", sa.String(80), nullable=False), sa.Column("event_id", sa.String(180), nullable=False), sa.Column("payload", postgresql.JSONB, nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"))


def downgrade() -> None:
    """Remove initial CRM tables in dependency order."""
    op.drop_table("webhook_events")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_ledger_entries_wallet_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_table("wallets")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
