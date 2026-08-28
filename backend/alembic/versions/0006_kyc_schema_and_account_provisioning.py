"""Add strict dynamic KYC schema and trading account provisioning state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_kyc_schema_and_account_provisioning"
down_revision = "0005_system_broadcasts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("kyc_schema", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("trading_accounts", sa.Column("provisioning_status", sa.String(20), nullable=False, server_default="PENDING"))


def downgrade() -> None:
    op.drop_column("trading_accounts", "provisioning_status")
    op.drop_column("tenant_settings", "kyc_schema")