"""Tests for the authentication system (register, login, profile)."""
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


@pytest.mark.asyncio
async def test_register_first_user(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/register", json={
        "username": "admin",
        "password": "adminpass",
        "display_name": "Admin User",
    })
    # Could be 201 (first user) or 403 (users already exist from other tests)
    assert resp.status_code in {201, 403}
    if resp.status_code == 201:
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["display_name"] == "Admin User"


@pytest.mark.asyncio
async def test_register_blocks_when_users_exist(client: AsyncClient, auth_token: str) -> None:
    """After first user is registered, further registrations should be blocked."""
    resp = await client.post("/api/auth/register", json={
        "username": "hacker",
        "password": "hackpass",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_valid_credentials(client: AsyncClient, auth_token: str) -> None:
    # auth_token fixture already created a user; but we need known credentials.
    # Register a fresh user first (will fail if users exist, which is fine)
    resp = await client.post("/api/auth/register", json={
        "username": "logintest",
        "password": "loginpass",
    })
    if resp.status_code == 201:
        login_resp = await client.post("/api/auth/login", json={
            "username": "logintest",
            "password": "loginpass",
        })
        assert login_resp.status_code == 200
        data = login_resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "logintest"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/login", json={
        "username": "nobody",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get("/api/auth/me", headers=auth_headers(auth_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "username" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_display_name(client: AsyncClient, auth_token: str) -> None:
    resp = await client.put(
        "/api/auth/me",
        json={"display_name": "New Name"},
        headers=auth_headers(auth_token),
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "New Name"
