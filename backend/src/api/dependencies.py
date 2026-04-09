from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.db.session import get_async_session as _get_async_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in _get_async_session():
        yield session
