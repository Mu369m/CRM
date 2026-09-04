"""Add precise provider connection outcomes."""

from alembic import op

revision = "0020_integration_statuses"
down_revision = "0019_trading_account_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in (
        "TESTING",
        "INVALID_CREDENTIALS",
        "PERMISSION_DENIED",
        "INVALID_CONFIGURATION",
        "PROVIDER_UNAVAILABLE",
        "TIMEOUT",
        "EXPIRED_CREDENTIAL",
        "CONNECTION_ERROR",
    ):
        op.execute(f"ALTER TYPE integrationstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    pass
