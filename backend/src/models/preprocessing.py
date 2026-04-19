from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    BigInteger,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.db.base import Base


class PropertyType(StrEnum):
    SALE = "SALE"
    RENT = "RENT"
    OTHER = "OTHER"
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    PLOT = "PLOT"
    LAND = "LAND"
    UNKNOWN = "UNKNOWN"


class TransactionType(StrEnum):
    RENT = "RENT"
    SALE = "SALE"
    UNKNOWN = "UNKNOWN"


class ListingIntent(StrEnum):
    OFFER = "OFFER"
    REQUEST = "REQUEST"
    UNKNOWN = "UNKNOWN"


class FurnishedType(StrEnum):
    FULLY_FURNISHED = "FULLY_FURNISHED"
    SEMI_FURNISHED = "SEMI_FURNISHED"
    FURNISHED = "FURNISHED"
    UNFURNISHED = "UNFURNISHED"
    UNKNOWN = "UNKNOWN"


class ListingStatus(StrEnum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class PropertyListing(Base):
    __tablename__ = "property_listings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("raw_message_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, name="property_type_enum"),
        nullable=False,
        default=PropertyType.OTHER,
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type_enum"),
        nullable=False,
        default=TransactionType.UNKNOWN,
    )
    listing_intent: Mapped[ListingIntent] = mapped_column(
        Enum(ListingIntent, name="listing_intent_enum"),
        nullable=False,
        default=ListingIntent.UNKNOWN,
    )
    bhk: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    furnished: Mapped[FurnishedType | None] = mapped_column(
        Enum(FurnishedType, name="furnished_type_enum"),
        nullable=True,
    )
    floor_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="listing_status_enum"),
        nullable=False,
        default=ListingStatus.PENDING,
    )
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    raw_chunk = relationship("RawMessageChunk")
    chunks: Mapped[list[ListingChunk]] = relationship(
        "ListingChunk",
        back_populates="listing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_property_listings_raw_chunk_id", "raw_chunk_id"),
        Index("ix_property_listings_property_type", "property_type"),
        Index("ix_property_listings_transaction_type", "transaction_type"),
        Index("ix_property_listings_listing_intent", "listing_intent"),
        Index("ix_property_listings_price", "price"),
        Index("ix_property_listings_status", "status"),
    )


class ListingChunk(Base):
    __tablename__ = "listing_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    listing: Mapped[PropertyListing] = relationship("PropertyListing", back_populates="chunks")

    __table_args__ = (
        Index("ix_listing_chunks_listing_id", "listing_id"),
        Index("ix_listing_chunks_qdrant_point_id", "qdrant_point_id"),
    )
