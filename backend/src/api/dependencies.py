from __future__ import annotations

from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.config import get_settings
from backend.src.db.session import get_async_session as _get_async_session

settings = get_settings()
_bearer_scheme = HTTPBearer(auto_error=False)

JWT_SECRET = settings.threadsense_admin_key if hasattr(settings, "threadsense_admin_key") else "change-me"
JWT_ALGORITHM = "HS256"


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in _get_async_session():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, str | None]:
    """Validate JWT and return user identity.

    Returns a dict with 'id' and 'username' keys.
    Raises 401 if no valid token is present.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str | None = payload.get("sub")
        username: str | None = payload.get("username")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"id": user_id, "username": username}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, str | None]:
    """Like get_current_user but returns empty dict instead of raising 401."""
    if credentials is None:
        return {"id": None, "username": None}

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"id": payload.get("sub"), "username": payload.get("username")}
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return {"id": None, "username": None}
