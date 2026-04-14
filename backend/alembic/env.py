import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your models so Alembic knows about them
from backend.src.db.diagnostics import PROBE_SQL, mask_database_url
from backend.src.db.base import Base, import_all_models
import_all_models()  # <-- this registers all models

target_metadata = Base.metadata

# Override the sqlalchemy.url from alembic.ini with environment variable
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@postgres:5432/threadsense",
    ),
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode (async)."""
    database_url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(database_url)
    x_args = context.get_x_argument(as_dictionary=True)

    async with connectable.connect() as connection:
        probe_row = (await connection.execute(PROBE_SQL)).one()
        print(
            "[alembic-db-probe]",
            {
                "database_url": mask_database_url(database_url),
                "current_database": probe_row[0],
                "current_schema": probe_row[1],
                "inet_server_addr": str(probe_row[2]) if probe_row[2] is not None else None,
                "inet_server_port": probe_row[3],
            },
        )

        if x_args.get("preflight", "").lower() in {"1", "true", "yes"}:
            await connectable.dispose()
            return

        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn,
                target_metadata=target_metadata,
            )
        )

        await connection.run_sync(lambda conn: context.run_migrations())

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
