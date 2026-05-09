from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID

from backend.src.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Application user for the self-hosted ThreadSense instance."""

    __tablename__ = "users"

    # id, email, hashed_password, is_active, is_superuser, is_verified are provided by SQLAlchemyBaseUserTableUUID
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"