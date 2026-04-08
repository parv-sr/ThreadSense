from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.db.base import Base


class RawFileStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RawMessageChunkStatus(StrEnum):
    NEW = "NEW"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"
    DUPLICATE_LOCAL = "DUPLICATE_LOCAL"


class RawFile(Base):
    """Represents an uploaded WhatsApp export .txt file."""

    __tablename__ = "raw_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    process_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    process_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_stats: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RawFileStatus.PENDING)
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    raw_chunks: Mapped[list[RawMessageChunk]] = relationship(
        back_populates="rawfile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_raw_files_uploaded_at", "uploaded_at"),
        Index("ix_raw_files_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"RawFile(id={self.id!s}, file_name={self.file_name!r}, "
            f"status={self.status!r}, processed={self.processed!r})"
        )

    def __str__(self) -> str:
        return f"{self.file_name} — uploaded {self.uploaded_at:%Y-%m-%d %H:%M}"


class RawMessageChunk(Base):
    """Each row represents a single WhatsApp message boundary."""

    __tablename__ = "raw_message_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rawfile_id: Mapped[UUID] = mapped_column(
        ForeignKey("raw_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    split_into: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RawMessageChunkStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    rawfile: Mapped[RawFile] = relationship(back_populates="raw_chunks")

    __table_args__ = (
        Index("ix_raw_message_chunks_message_start", "message_start"),
        Index("ix_raw_message_chunks_sender", "sender"),
        Index("ix_raw_message_chunks_status", "status"),
        Index("ix_raw_message_chunks_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"RawMessageChunk(id={self.id!s}, rawfile_id={self.rawfile_id!s}, "
            f"sender={self.sender!r}, status={self.status!r})"
        )

    def __str__(self) -> str:
        preview = (self.cleaned_text or self.raw_text)[:80].replace("\n", " ")
        return f"{self.sender or 'Unknown'} @ {self.message_start} — {preview}..."


class FileProcess(Base):
    __tablename__ = "file_processes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False, default="Queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("ix_file_processes_created_at", "created_at"),)

    def __repr__(self) -> str:
        return (
            f"FileProcess(id={self.id!s}, file={self.file!r}, "
            f"status={self.status!r}, progress={self.progress!r})"
        )

    def __str__(self) -> str:
        return f"Processing {self.file} ({self.progress}%)"
