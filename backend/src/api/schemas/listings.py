from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ListingOut(BaseModel):
    id: str
    transaction_type: str
    property_type: str
    listing_intent: str
    price: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    price_status: str
    bhk: float | None = None
    sqft: int | None = None
    location: str | None = None
    canonical_location: str | None = None
    furnishing: str | None = None
    floor_band: str | None = None
    price_per_sqft: int | None = None
    has_contact: bool | None = None
    pets_allowed: bool | None = None
    suspicious_flags: list[str] = Field(default_factory=list)
    confidence_score: float
    sender: str | None = None
    timestamp: datetime | None = None
    contact_number: str | None = None
    semantic_score: float | None = None


class ListingsResponse(BaseModel):
    items: list[ListingOut]
    total: int
    limit: int
    offset: int


class FacetBucket(BaseModel):
    value: str
    count: int


class FacetsResponse(BaseModel):
    transaction_type: list[FacetBucket]
    property_type: list[FacetBucket]
    canonical_location: list[FacetBucket]
    bhk: list[FacetBucket]
    furnishing: list[FacetBucket]


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1)


class BulkDeleteResponse(BaseModel):
    deleted: int
