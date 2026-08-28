"""Add trader profile fields and structured KYC submission data."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_trader_profile_kyc"
down_revision = "0008_risk_monitoring_and_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(160)))
    op.add_column("users", sa.Column("phone", sa.String(40)))
    op.add_column("users", sa.Column("country", sa.String(2)))
    op.add_column("users", sa.Column("address", sa.Text()))
    op.add_column("kyc_documents", sa.Column("submission_data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column("kyc_documents", "submission_data")
    op.drop_column("users", "address")
    op.drop_column("users", "country")
    op.drop_column("users", "phone")
    op.drop_column("users", "full_name")