from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    EMBEDDED = "EMBEDDED"


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


class ORMBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RawFileBase(BaseModel):
    file: str
    file_name: str = Field(max_length=255)
    content: str = ""
    source: str | None = None
    processed: bool = False
    process_started_at: datetime | None = None
    process_finished_at: datetime | None = None
    notes: str | None = None
    dedupe_stats: dict[str, Any] = Field(default_factory=dict)
    status: RawFileStatus = RawFileStatus.PENDING
    owner_id: UUID | None = None
    last_heartbeat_at: datetime | None = None


class RawFileCreate(RawFileBase):
    pass


class RawFileUpdate(BaseModel):
    file: str | None = None
    file_name: str | None = Field(default=None, max_length=255)
    content: str | None = None
    source: str | None = None
    processed: bool | None = None
    process_started_at: datetime | None = None
    process_finished_at: datetime | None = None
    notes: str | None = None
    dedupe_stats: dict[str, Any] | None = None
    status: RawFileStatus | None = None
    owner_id: UUID | None = None
    last_heartbeat_at: datetime | None = None


class RawFileOut(ORMBaseSchema, RawFileBase):
    id: UUID
    uploaded_at: datetime


class RawFileResponse(BaseModel):
    data: RawFileOut


class RawMessageChunkBase(BaseModel):
    rawfile_id: UUID
    message_start: datetime | None = None
    sender: str | None = Field(default=None, max_length=255)
    raw_text: str
    cleaned_text: str | None = None
    split_into: int = 0
    status: RawMessageChunkStatus = RawMessageChunkStatus.NEW
    user_id: UUID | None = None


class RawMessageChunkCreate(RawMessageChunkBase):
    pass


class RawMessageChunkUpdate(BaseModel):
    message_start: datetime | None = None
    sender: str | None = Field(default=None, max_length=255)
    raw_text: str | None = None
    cleaned_text: str | None = None
    split_into: int | None = None
    status: RawMessageChunkStatus | None = None
    user_id: UUID | None = None


class RawMessageChunkOut(ORMBaseSchema, RawMessageChunkBase):
    id: UUID
    created_at: datetime


class RawMessageChunkResponse(BaseModel):
    data: RawMessageChunkOut


class FileProcessBase(BaseModel):
    file: str
    status: str = "Queued"
    progress: int = 0


class FileProcessCreate(FileProcessBase):
    pass


class FileProcessUpdate(BaseModel):
    file: str | None = None
    status: str | None = None
    progress: int | None = None


class FileProcessOut(ORMBaseSchema, FileProcessBase):
    id: UUID
    created_at: datetime


class FileProcessResponse(BaseModel):
    data: FileProcessOut


class PropertyListingBase(BaseModel):
    raw_chunk_id: UUID
    transaction_type: TransactionType = TransactionType.UNKNOWN
    property_type: PropertyType = PropertyType.UNKNOWN
    listing_intent: ListingIntent = ListingIntent.UNKNOWN
    price: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    price_status: PriceStatus = PriceStatus.CALL_FOR_PRICE
    bhk: float | None = None
    sqft: int | None = None
    location: str | None = Field(default=None, max_length=255)
    canonical_location: str | None = Field(default=None, max_length=255)
    furnishing: Furnishing | None = None
    pets_allowed: bool | None = None
    suspicious_flags: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    contact_number: str | None = Field(default=None, max_length=64)
    sender: str | None = Field(default=None, max_length=255)
    timestamp: datetime | None = None
    floor_number: int | None = None
    total_floors: int | None = None
    landmark: str | None = Field(default=None, max_length=255)
    is_verified: bool = False
    status: ListingStatus = ListingStatus.PENDING
    raw_llm_output: str | None = None


class PropertyListingCreate(PropertyListingBase):
    pass


class PropertyListingUpdate(BaseModel):
    transaction_type: TransactionType | None = None
    property_type: PropertyType | None = None
    listing_intent: ListingIntent | None = None
    price: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    price_status: PriceStatus | None = None
    bhk: float | None = None
    sqft: int | None = None
    location: str | None = Field(default=None, max_length=255)
    canonical_location: str | None = Field(default=None, max_length=255)
    furnishing: Furnishing | None = None
    pets_allowed: bool | None = None
    suspicious_flags: list[str] | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ListingStatus | None = None


class PropertyListingOut(ORMBaseSchema, PropertyListingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ListingChunkBase(BaseModel):
    property_listing_id: UUID
    content: str
    chunk_index: int = 0


class ListingChunkCreate(ListingChunkBase):
    embedding: list[float] | None = None


class ListingChunkOut(ORMBaseSchema, ListingChunkBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ParseRawFileTaskPayload(BaseModel):
    rawfile_id: UUID


class RawFileProcessResult(BaseModel):
    rawfile_id: UUID
    created: int
    ignored: int
    completed_at: datetime


class ChunkEmbedTaskPayload(BaseModel):
    raw_message_chunk_id: UUID


class ChunkStatusUpdatePayload(BaseModel):
    raw_message_chunk_id: UUID
    status: RawMessageChunkStatus
