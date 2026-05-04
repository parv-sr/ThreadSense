from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType

try:
    from pgvector.sqlalchemy import Vector
except ModuleNotFoundError:  # pragma: no cover - local fallback until pgvector is installed.
    class Vector(UserDefinedType):  # type: ignore[no-redef]
        cache_ok = True

        def __init__(self, dimensions: int) -> None:
            self.dimensions = dimensions

        def get_col_spec(self, **_: Any) -> str:
            return f"VECTOR({self.dimensions})"

        class comparator_factory(UserDefinedType.Comparator):
            def cosine_distance(self, other: Any) -> Any:
                return self.op("<=>")(other)

from backend.src.db.base import Base


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_cls]


class TransactionType(StrEnum):
    RENT = "RENT"
    SALE = "SALE"
    LEASE = "LEASE"
    UNKNOWN = "UNKNOWN"


class PropertyType(StrEnum):
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    PLOT = "PLOT"
    LAND = "LAND"
    UNKNOWN = "UNKNOWN"


class ListingIntent(StrEnum):
    OFFER = "OFFER"
    REQUEST = "REQUEST"
    UNKNOWN = "UNKNOWN"


class PriceStatus(StrEnum):
    EXACT = "EXACT"
    RANGE = "RANGE"
    CALL_FOR_PRICE = "CALL_FOR_PRICE"
    MARKET_PRICE = "MARKET_PRICE"


class Furnishing(StrEnum):
    FULLY_FURNISHED = "FULLY-FURNISHED"
    SEMI_FURNISHED = "SEMI-FURNISHED"
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

    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transaction_type_enum",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=TransactionType.UNKNOWN,
    )
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(
            PropertyType,
            name="property_type_enum",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=PropertyType.UNKNOWN,
    )
    listing_intent: Mapped[ListingIntent] = mapped_column(
        Enum(
            ListingIntent,
            name="listing_intent_enum",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ListingIntent.UNKNOWN,
    )
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_status: Mapped[PriceStatus] = mapped_column(
        Enum(
            PriceStatus,
            name="price_status_enum",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=PriceStatus.CALL_FOR_PRICE,
    )
    bhk: Mapped[float | None] = mapped_column(Float, nullable=True)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    furnishing: Mapped[Furnishing | None] = mapped_column(
        Enum(
            Furnishing,
            name="furnishing_enum",
            values_callable=_enum_values,
        ),
        nullable=True,
    )
    pets_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suspicious_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    contact_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    floor_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="listing_status_enum", values_callable=_enum_values),
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

    raw_chunk = relationship("RawMessageChunk", back_populates="property_listing")
    chunks: Mapped[list[ListingChunk]] = relationship(
        "ListingChunk",
        back_populates="listing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_property_listings_raw_chunk_id", "raw_chunk_id"),
        Index("ix_property_listings_transaction_type", "transaction_type"),
        Index("ix_property_listings_property_type", "property_type"),
        Index("ix_property_listings_listing_intent", "listing_intent"),
        Index("ix_property_listings_price", "price"),
        Index("ix_property_listings_price_min", "price_min"),
        Index("ix_property_listings_price_max", "price_max"),
        Index("ix_property_listings_price_status", "price_status"),
        Index("ix_property_listings_bhk", "bhk"),
        Index("ix_property_listings_sqft", "sqft"),
        Index("ix_property_listings_canonical_location", "canonical_location"),
        Index("ix_property_listings_furnishing", "furnishing"),
        Index("ix_property_listings_status", "status"),
    )


class ListingChunk(Base):
    __tablename__ = "listing_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    property_listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
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
        Index("ix_listing_chunks_property_listing_id", "property_listing_id"),
        Index("ix_listing_chunks_created_at", "created_at"),
    )


FurnishedType = Furnishing
