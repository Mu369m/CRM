"""Create master system broadcast storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_system_broadcasts"
down_revision = "0004_supplied_crm_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_broadcasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broadcast_type", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("target_brokers", sa.String(30), server_default="ALL_BROKERS", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_broadcasts_enabled_updated", "system_broadcasts", ["enabled", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_system_broadcasts_enabled_updated", table_name="system_broadcasts")
    op.drop_table("system_broadcasts")