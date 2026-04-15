from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from typing import AsyncGenerator
from backend.src.core.config import get_settings

class Base(DeclarativeBase):
    """Base class for all models."""
    pass

settings = get_settings()
DATABASE_URL = settings.database_url

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
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
    from backend.src.models.preprocessing import (  # noqa: F401
        ListingChunk,
        PropertyListing,
    )
    from backend.src.models.users import User # noqa: F401
