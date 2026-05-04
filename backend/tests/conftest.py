"""Shared test fixtures for the ThreadSense backend test suite.

Provides an in-process test database (PostgreSQL via CI service or
local), applies Alembic migrations, and exposes an async httpx client
wired to the FastAPI application with a mocked Celery broker.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Environment defaults for CI (GitHub Actions provides a PostgreSQL service)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://threadsense:threadsense@localhost:5432/threadsense_test",
)

# Override the DATABASE_URL before any app module is imported so that
# `get_settings()` picks up the test database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["THREADSENSE_ADMIN_KEY"] = "test-secret-key"
os.environ["APP_ENV"] = "test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class FakeTaskHandle:
    task_id: str


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine and run Alembic migrations once."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Run migrations
    from backend.src.db.base import import_all_models
    import_all_models()

    from backend.src.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the FastAPI app with mocked broker.

    The broker's task().kiq() is mocked to return a fake task handle
    so tests never need a real Redis/Celery connection.
    """
    # Patch the session factory to use our test engine
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    # Mock the broker's kiq calls
    fake_kiq = AsyncMock(return_value=FakeTaskHandle(task_id=str(uuid4())))

    with patch("backend.src.tasks.ingestion.ingest_raw_file_task.kiq", fake_kiq):
        from backend.src.main import app
        from backend.src.api.dependencies import get_db_session

        app.dependency_overrides[get_db_session] = _override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, test_engine) -> str:
    """Create a test user and return a valid JWT token."""
    from backend.src.api.auth_config import UserCreate, UserManager
    from backend.src.models.users import User
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        user_manager = UserManager(user_db)
        
        email = f"testuser_{uuid4().hex[:8]}@test.local"
        user_create = UserCreate(
            email=email,
            password="testpass123",
            username=email,
            display_name="Test User",
            is_active=True,
            is_verified=True,
        )
        try:
            await user_manager.create(user_create)
        except Exception:
            pass

    resp = await client.post(
        "/api/auth/login",
        data={
            "username": email,
            "password": "testpass123",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    data = resp.json()
    return data["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    """Build authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {token}"}
