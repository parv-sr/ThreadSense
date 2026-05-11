from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config

log = structlog.get_logger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[1]

def _fix_orphaned_revision(alembic_cfg: Config) -> None:
    """Replace the orphaned revision in alembic_version with the current head.

    Uses asyncpg directly because Alembic's own stamp command also
    reads the orphaned revision through env.py and crashes.
    """
    import os
    import asyncpg
    from alembic.script import ScriptDirectory

    async_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://threadsense:threadsense@db:5432/threadsense",
    )
    dsn = async_url.replace("postgresql+asyncpg://", "postgresql://")
    script = ScriptDirectory.from_config(alembic_cfg)
    head = script.get_current_head()
    log.warning("fixing_orphaned_revision", stamping_to=head, action="direct SQL update")

    async def _do_fix() -> None:
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("DELETE FROM alembic_version")
            await conn.execute("INSERT INTO alembic_version (version_num) VALUES ($1)", head)
        finally:
            await conn.close()

    asyncio.run(_do_fix())


def _run_alembic_upgrade() -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        # If the DB is stamped at a revision that no longer exists in the
        # migration files (e.g. after a git rebase), fix it with raw SQL
        # because command.stamp() also fails on orphaned revisions.
        if "Can't locate revision" in str(exc):
            _fix_orphaned_revision(alembic_cfg)
            command.upgrade(alembic_cfg, "head")
        else:
            raise


async def run_migrations() -> None:
    log.info("migrations_running")
    await asyncio.to_thread(_run_alembic_upgrade)
    log.info("migrations_applied")


async def create_superuser() -> None:
    from backend.src.core.config import get_settings
    from backend.src.db.session import AsyncSessionLocal
    from backend.src.models.users import User
    from backend.src.api.auth_config import UserManager, UserCreate
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        user_manager = UserManager(user_db)
        
        email = f"{settings.threadsense_admin_username}@threadsense.com"
        # Just use the username config for email login if they use standard forms
        # fastapi-users uses email as the primary login identifier
        existing = await user_db.get_by_email(email)
        if not existing:
            user_create = UserCreate(
                email=email,
                password=settings.threadsense_admin_password,
                is_superuser=True,
                is_active=True,
                is_verified=True,
                username=settings.threadsense_admin_username,
                display_name="Administrator",
            )
            await user_manager.create(user_create)
            log.info("superuser_created", email=email)
        else:
            if not existing.is_superuser or not existing.is_verified:
                existing.is_superuser = True
                existing.is_verified = True
                await session.commit()
                log.info("superuser_updated", email=email)


async def _repair_schema() -> None:
    """Ensure columns expected by the ORM exist in the database.

    This covers the case where alembic_version was force-stamped to
    head (skipping migration 6e4d774441f4).  Uses ADD COLUMN IF NOT
    EXISTS so it is harmless when columns already exist.
    """
    from backend.src.db.session import AsyncSessionLocal
    from sqlalchemy import text

    patches = [
        "ALTER TABLE property_listings ADD COLUMN IF NOT EXISTS floor_band VARCHAR(50)",
        "ALTER TABLE property_listings ADD COLUMN IF NOT EXISTS price_per_sqft INTEGER",
        "ALTER TABLE property_listings ADD COLUMN IF NOT EXISTS landmark VARCHAR(255)",
        "ALTER TABLE property_listings ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT false",
    ]

    async with AsyncSessionLocal() as session:
        for sql in patches:
            await session.execute(text(sql))
        await session.commit()
        log.info("schema_repair_complete")


async def initialize_infrastructure() -> None:
    await run_migrations()
    await _repair_schema()
    try:
        await create_superuser()
    except Exception as exc:  # noqa: BLE001
        log.error("superuser_creation_failed", error=str(exc), exc_info=True)


if __name__ == "__main__":
    asyncio.run(initialize_infrastructure())
