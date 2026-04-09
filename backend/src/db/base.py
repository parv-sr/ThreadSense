from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from typing import AsyncGenerator

class Base(DeclarativeBase):
    """Base class for all models."""
    pass

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/threadsense",
)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    echo=False,  # set True only in dev if needed
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

def import_all_models() -> None:
    """Import all model modules so SQLAlchemy metadata is fully registered."""
    from backend.src.models.ingestion import (  # noqa: F401
        FileProcess,
        RawFile,
        RawMessageChunk,
    )