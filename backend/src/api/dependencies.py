from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.config import get_settings
from backend.src.db.session import get_async_session as _get_async_session

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in _get_async_session():
        yield session


# ---------------------------------------------------------------------------
# Auth: verify Supabase JWT via the Supabase Auth API
#
# Why not local JWT decode?
# The project's Supabase instance issues user tokens signed with ES256
# (ECDSA P-256).  PyJWT requires the `cryptography` package for EC/RSA
# algorithms, which is not installed in this container image.  Verifying
# via the Supabase /auth/v1/user endpoint is the canonical server-side
# approach: it works with any signing algorithm, automatically handles
# key rotation, and returns a rich user object with no extra dependencies.
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Validate a Supabase Bearer token and return the user dict."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    settings = get_settings()

    supabase_url = settings.supabase_url
    anon_key = settings.supabase_anon_key
    if not supabase_url or not anon_key:
        log.error("Supabase URL or anon key not configured on server")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service is not configured",
        )

    url = f"{supabase_url.rstrip('/')}/auth/v1/user"
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        log.warning("Supabase auth request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach authentication service",
        )

    if resp.status_code == 200:
        user = resp.json()
        return {"id": user.get("id"), "email": user.get("email")}

    # Token invalid or expired
    log.debug("Supabase auth rejected token: HTTP %s", resp.status_code)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
