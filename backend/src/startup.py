from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config

log = structlog.get_logger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _get_alembic_head(alembic_cfg: Config) -> str:
    """Return the current head revision id from the migration scripts."""
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(alembic_cfg)
    return script.get_current_head()


def _fix_orphaned_revision(alembic_cfg: Config) -> None:
    """Directly UPDATE alembic_version in the DB, bypassing env.py entirely."""
    import os
    import asyncpg

    async_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://threadsense:threadsense@db:5432/threadsense",
    )
    # Convert SQLAlchemy URL to plain DSN for asyncpg
    dsn = async_url.replace("postgresql+asyncpg://", "postgresql://")
    head = _get_alembic_head(alembic_cfg)
    log.warning("fixing_orphaned_revision", new_head=head, action="direct SQL update")

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


async def initialize_infrastructure() -> None:
    await run_migrations()
    try:
        await create_superuser()
    except Exception as exc:  # noqa: BLE001
        log.error("superuser_creation_failed", error=str(exc), exc_info=True)


if __name__ == "__main__":
    asyncio.run(initialize_infrastructure())
