from uuid import UUID, uuid4
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.db.base import Base


class User(Base):
    """Minimal User model to satisfy foreign key references."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.email}>"