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


async def initialize_infrastructure() -> None:
    await run_migrations()


if __name__ == "__main__":
    asyncio.run(initialize_infrastructure())
