from __future__ import annotations

import structlog
from fastapi import APIRouter

from backend.src.api.auth_config import (
    UserCreate,
    UserRead,
    UserUpdate,
    auth_backend,
    fastapi_users,
)

router = APIRouter()
log = structlog.get_logger(__name__)

@router.get("/auth/bootstrap", tags=["auth"])
async def bootstrap_check() -> dict[str, bool]:
    """Check if any users exist. Always false now since we use .env admin."""
    return {"needs_setup": False}

# fastapi-users standard routes
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
