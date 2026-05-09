from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, schemas
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.core.config import get_settings
from backend.src.models.users import User

settings = get_settings()
SECRET = settings.threadsense_admin_key


# ── Schemas ───────────────────────────────────────────────────────────────

class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str
    display_name: str


class UserCreate(schemas.BaseUserCreate):
    username: str
    display_name: str


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    display_name: Optional[str] = None


# ── Database & Manager ────────────────────────────────────────────────────

async def get_user_db(session: AsyncSession = Depends(get_db_session)):
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


# ── Authentication Backend ────────────────────────────────────────────────

bearer_transport = BearerTransport(tokenUrl="auth/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600 * 24 * 7)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# ── FastAPI Users ─────────────────────────────────────────────────────────

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
