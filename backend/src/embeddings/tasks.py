from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select

from backend.src.db.session import AsyncSessionLocal
from backend.src.embeddings.service import EmbeddingService
from backend.src.models.preprocessing import ListingChunk, PropertyListing
from backend.src.tasks import broker

log = structlog.get_logger(__name__)


@broker.task
async def embed_property_listing_task(listing_id: str) -> dict[str, str]:
    _log = log.bind(listing_id=listing_id)
    _log.info("embedding_started")

    try:
        parsed_id = UUID(listing_id)
    except ValueError as exc:
        return {"status": "FAILED", "error": f"Invalid listing_id: {exc}"}

    async with AsyncSessionLocal() as session:
        listing = await session.get(PropertyListing, parsed_id)
        if listing is None:
            return {"status": "FAILED", "error": "Listing not found"}

        stmt = (
            select(ListingChunk)
            .where(ListingChunk.property_listing_id == parsed_id)
            .order_by(ListingChunk.chunk_index)
        )
        chunks = list((await session.execute(stmt)).scalars().all())
        if not chunks:
            return {"status": "FAILED", "error": "No listing chunks to embed"}

        service = EmbeddingService()
        try:
            await service.embed_and_upsert_listing(listing=listing, session=session)
            await session.commit()
            _log.info("embedding_completed", chunk_count=len(chunks))
        finally:
            await service.close()

    return {"status": "COMPLETED", "listing_id": listing_id}
