from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.src.core.config import get_settings


settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
