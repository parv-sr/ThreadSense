from __future__ import annotations

from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from backend.src.db.session import AsyncSessionLocal
from backend.src.embeddings.service import EmbeddingService
from backend.src.models.preprocessing import ListingChunk, PropertyListing
from backend.src.tasks import broker

log = structlog.get_logger(__name__)


@broker.task
async def embed_property_listing_task(listing_id: str) -> dict[str, str]:
    log.info("embed_listing_task_started", listing_id=listing_id)
    try:
        parsed_id = UUID(listing_id)
    except ValueError as exc:
        return {"status": "FAILED", "error": f"Invalid listing_id: {exc}"}

    async with AsyncSessionLocal() as session:
        listing = await session.get(PropertyListing, parsed_id)
        if listing is None:
            return {"status": "FAILED", "error": "Listing not found"}

        stmt = select(ListingChunk).where(ListingChunk.listing_id == parsed_id).order_by(ListingChunk.chunk_index)
        chunks = list((await session.execute(stmt)).scalars().all())
        if not chunks:
            return {"status": "FAILED", "error": "No listing chunks to embed"}
        log.info("embed_listing_chunks_loaded", listing_id=listing_id, chunk_count=len(chunks))

        service = EmbeddingService()
        try:
            await service.ensure_collection()
            for chunk in chunks:
                vector = await service.embed_text(chunk.content)
                point_id = chunk.qdrant_point_id or str(uuid4())
                await service.upsert_listing_vector(
                    point_id=point_id,
                    vector=vector,
                    listing=listing,
                    chunk_content=chunk.content,
                )
                chunk.qdrant_point_id = point_id
                session.add(chunk)
                log.debug(
                    "embed_listing_chunk_upserted",
                    listing_id=listing_id,
                    chunk_id=str(chunk.id),
                    point_id=point_id,
                    vector_size=len(vector),
                )

            await session.commit()
            log.info("embed_listing_commit_complete", listing_id=listing_id, chunk_count=len(chunks))
        finally:
            await service.close()
            log.info("embed_listing_service_closed", listing_id=listing_id)

    log.info("embed_listing_done", listing_id=listing_id, chunk_count=len(chunks))
    return {"status": "COMPLETED", "listing_id": listing_id}
