from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_current_user, get_db_session
from backend.src.core.config import get_settings
from backend.src.models.users import User

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger(__name__)
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = settings.threadsense_admin_key if hasattr(settings, "threadsense_admin_key") else "change-me"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


# ── Request / Response schemas ────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    is_active: bool


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=4, max_length=128)


# ── Helpers ───────────────────────────────────────────────────────────────

def _create_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name or user.username,
        email=user.email,
        is_active=user.is_active,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/bootstrap")
async def bootstrap_check(session: AsyncSession = Depends(get_db_session)) -> dict[str, bool]:
    """Check if any users exist. Frontend uses this to decide whether to show
    the registration form or the login form."""
    count = (await session.execute(select(func.count(User.id)))).scalar_one()
    return {"needs_setup": count == 0}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    # Only allow registration when no users exist (first-run bootstrap)
    count = (await session.execute(select(func.count(User.id)))).scalar_one()
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Contact your admin.",
        )

    existing = (await session.execute(
        select(User).where(User.username == body.username)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        username=body.username,
        email=f"{body.username}@threadsense.local",
        display_name=body.display_name or body.username,
        hashed_password=pwd_context.hash(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    log.info("user_registered", username=user.username, user_id=str(user.id))

    token = _create_token(str(user.id), user.username)
    return TokenResponse(access_token=token, user=_user_response(user))


@router.post("/login")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user = (await session.execute(
        select(User).where(User.username == body.username)
    )).scalar_one_or_none()

    if user is None or not pwd_context.verify(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = _create_token(str(user.id), user.username)
    log.info("user_login", username=user.username)
    return TokenResponse(access_token=token, user=_user_response(user))


@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from uuid import UUID
    user = await session.get(User, UUID(user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return _user_response(user)


@router.put("/me")
async def update_me(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from uuid import UUID
    user = await session.get(User, UUID(user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.display_name is not None:
        user.display_name = body.display_name

    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password required to set new password")
        if not pwd_context.verify(body.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.hashed_password = pwd_context.hash(body.new_password)

    await session.commit()
    await session.refresh(user)
    log.info("user_profile_updated", username=user.username)
    return _user_response(user)
