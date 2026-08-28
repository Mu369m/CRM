"""Remote tenant migration runner for BYODB onboarding."""

import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

_migration_lock = asyncio.Lock()


async def migrate_tenant_database(database_url: str) -> None:
    """Run the checked-in Alembic chain against one verified private database."""
    async with _migration_lock:
        def run() -> None:
            config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
            config.set_main_option("script_location", str(Path(__file__).parents[2] / "alembic"))
            os.environ["ALEMBIC_DATABASE_URL"] = database_url
            try:
                command.upgrade(config, "head")
            finally:
                os.environ.pop("ALEMBIC_DATABASE_URL", None)
        await asyncio.to_thread(run)
