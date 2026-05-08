"""Tests for the authentication system (login, profile) using fastapi-users."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_bootstrap_check_empty_db(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/bootstrap")
    assert resp.status_code == 200
    data = resp.json()
    assert "needs_setup" in data
    assert data["needs_setup"] is False


@pytest.mark.asyncio
async def test_login_valid_credentials(client: AsyncClient, test_engine) -> None:
    from backend.src.api.auth_config import UserCreate, UserManager
    from backend.src.models.users import User
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from sqlalchemy.ext.asyncio import async_sessionmaker

    # 1. Explicitly seed a known test user into the database
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        user_manager = UserManager(user_db)
        
        email = "validlogin@test.local"
        password = "securepassword123"
        user_create = UserCreate(
            email=email,
            password=password,
            username=email,
            display_name="Login Test",
            is_active=True,
            is_verified=True,
        )
        try:
            await user_manager.create(user_create)
        except Exception:
            pass # Ignore if user already exists from a previous aborted run

    # 2. Attempt to log in with the exact credentials we just created
    resp = await client.post(
        "/api/auth/login",
        data={
            "username": email,
            "password": password,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/login",
        data={
            "username": "admin@threadsense.com",
            "password": "wrongpass",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    # fastapi-users returns 400 Bad Request for wrong credentials
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get("/api/users/me", headers=auth_headers(auth_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_display_name(client: AsyncClient, auth_token: str) -> None:
    resp = await client.patch(
        "/api/users/me",
        json={"display_name": "New Name"},
        headers=auth_headers(auth_token),
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "New Name"
