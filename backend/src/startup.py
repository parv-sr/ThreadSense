from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config

log = structlog.get_logger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic_upgrade() -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


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
    await create_superuser()


if __name__ == "__main__":
    asyncio.run(initialize_infrastructure())
