from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.api.schemas.listings import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    FacetBucket,
    FacetsResponse,
    ListingOut,
    ListingsResponse,
)
from backend.src.embeddings.service import EmbeddingService
from backend.src.models.preprocessing import ListingChunk, PropertyListing

router = APIRouter(prefix="/listings", tags=["listings"])
logger = structlog.get_logger(__name__)


def _enum_value(value: object) -> str:
    return getattr(value, "value", str(value))


def _listing_out(listing: PropertyListing, semantic_distance: float | None = None) -> ListingOut:
    return ListingOut(
        id=str(listing.id),
        transaction_type=_enum_value(listing.transaction_type),
        property_type=_enum_value(listing.property_type),
        listing_intent=_enum_value(listing.listing_intent),
        price=listing.price,
        price_min=listing.price_min,
        price_max=listing.price_max,
        price_status=_enum_value(listing.price_status),
        bhk=listing.bhk,
        sqft=listing.sqft,
        location=listing.location,
        canonical_location=listing.canonical_location,
        furnishing=_enum_value(listing.furnishing) if listing.furnishing is not None else None,
        pets_allowed=listing.pets_allowed,
        suspicious_flags=listing.suspicious_flags or [],
        confidence_score=listing.confidence_score,
        sender=listing.sender,
        timestamp=listing.timestamp,
        contact_number=listing.contact_number,
        semantic_score=(max(0.0, 1.0 - semantic_distance) if semantic_distance is not None else None),
    )


def _normalize_canonical_location(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _apply_filters(
    stmt,
    *,
    transaction_type: list[str] | None,
    property_type: list[str] | None,
    listing_intent: list[str] | None,
    canonical_location: str | None,
    furnishing: list[str] | None,
    bhk: list[float] | None,
    min_price: int | None,
    max_price: int | None,
    min_sqft: int | None,
    max_sqft: int | None,
):
    if transaction_type:
        stmt = stmt.where(PropertyListing.transaction_type.in_([item.upper() for item in transaction_type]))
    if property_type:
        stmt = stmt.where(PropertyListing.property_type.in_([item.upper() for item in property_type]))
    if listing_intent:
        stmt = stmt.where(PropertyListing.listing_intent.in_([item.upper() for item in listing_intent]))
    if canonical_location:
        stmt = stmt.where(PropertyListing.canonical_location == _normalize_canonical_location(canonical_location))
    if furnishing:
        stmt = stmt.where(PropertyListing.furnishing.in_([item.upper().replace("_", "-") for item in furnishing]))
    if bhk:
        exact_bhk = [item for item in bhk if item < 4]
        bhk_conditions = []
        if exact_bhk:
            bhk_conditions.append(PropertyListing.bhk.in_(exact_bhk))
        if any(item >= 4 for item in bhk):
            bhk_conditions.append(PropertyListing.bhk >= 4)
        stmt = stmt.where(or_(*bhk_conditions))
    if min_price is not None:
        stmt = stmt.where(PropertyListing.price_min >= min_price)
    if max_price is not None:
        stmt = stmt.where(PropertyListing.price_max <= max_price)
    if min_sqft is not None:
        stmt = stmt.where(PropertyListing.sqft >= min_sqft)
    if max_sqft is not None:
        stmt = stmt.where(PropertyListing.sqft <= max_sqft)
    return stmt


async def _facet(session: AsyncSession, column) -> list[FacetBucket]:
    rows = (
        await session.execute(
            select(column, func.count(PropertyListing.id))
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count(PropertyListing.id).desc(), column)
            .limit(100)
        )
    ).all()
    return [FacetBucket(value=str(value), count=int(count)) for value, count in rows]


@router.get("/facets", response_model=FacetsResponse)
async def listing_facets(session: AsyncSession = Depends(get_db_session)) -> FacetsResponse:
    return FacetsResponse(
        transaction_type=await _facet(session, PropertyListing.transaction_type),
        property_type=await _facet(session, PropertyListing.property_type),
        canonical_location=await _facet(session, PropertyListing.canonical_location),
        bhk=await _facet(session, PropertyListing.bhk),
        furnishing=await _facet(session, PropertyListing.furnishing),
    )


@router.get("", response_model=ListingsResponse)
async def list_listings(
    session: AsyncSession = Depends(get_db_session),
    transaction_type: list[str] | None = Query(default=None),
    property_type: list[str] | None = Query(default=None),
    listing_intent: list[str] | None = Query(default=None),
    canonical_location: str | None = None,
    furnishing: list[str] | None = Query(default=None),
    bhk: list[float] | None = Query(default=None),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    min_sqft: int | None = Query(default=None, ge=0),
    max_sqft: int | None = Query(default=None, ge=0),
    semantic_q: str | None = Query(default=None, max_length=1000),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ListingsResponse:
    count_stmt = _apply_filters(
        select(func.count(PropertyListing.id)),
        transaction_type=transaction_type,
        property_type=property_type,
        listing_intent=listing_intent,
        canonical_location=canonical_location,
        furnishing=furnishing,
        bhk=bhk,
        min_price=min_price,
        max_price=max_price,
        min_sqft=min_sqft,
        max_sqft=max_sqft,
    )
    total = int((await session.execute(count_stmt)).scalar_one())

    if semantic_q:
        embedding = await EmbeddingService().embed_text(semantic_q)
        distance = ListingChunk.embedding.cosine_distance(embedding).label("semantic_distance")
        stmt = (
            select(PropertyListing, distance)
            .join(ListingChunk, ListingChunk.property_listing_id == PropertyListing.id)
            .where(ListingChunk.embedding.is_not(None))
        )
        stmt = _apply_filters(
            stmt,
            transaction_type=transaction_type,
            property_type=property_type,
            listing_intent=listing_intent,
            canonical_location=canonical_location,
            furnishing=furnishing,
            bhk=bhk,
            min_price=min_price,
            max_price=max_price,
            min_sqft=min_sqft,
            max_sqft=max_sqft,
        )
        rows = (await session.execute(stmt.order_by(distance).offset(offset).limit(limit))).all()
        items = [_listing_out(listing, float(distance_value)) for listing, distance_value in rows]
    else:
        stmt = _apply_filters(
            select(PropertyListing),
            transaction_type=transaction_type,
            property_type=property_type,
            listing_intent=listing_intent,
            canonical_location=canonical_location,
            furnishing=furnishing,
            bhk=bhk,
            min_price=min_price,
            max_price=max_price,
            min_sqft=min_sqft,
            max_sqft=max_sqft,
        )
        stmt = stmt.order_by(PropertyListing.updated_at.desc()).offset(offset).limit(limit)
        items = [_listing_out(listing) for listing in (await session.execute(stmt)).scalars().all()]

    logger.info("listings_search_complete", total=total, returned=len(items), semantic=bool(semantic_q))
    return ListingsResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/delete", response_model=BulkDeleteResponse)
async def delete_listings(
    payload: BulkDeleteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BulkDeleteResponse:
    ids: list[UUID] = []
    for item in payload.ids:
        try:
            ids.append(UUID(item))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid listing id: {item}") from exc

    result = await session.execute(delete(PropertyListing).where(PropertyListing.id.in_(ids)))
    await session.commit()
    return BulkDeleteResponse(deleted=int(result.rowcount or 0))
