from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.ingestion import RawMessageChunk, RawMessageChunkStatus
from backend.src.models.preprocessing import ListingChunk, ListingStatus, PropertyListing
from backend.src.preprocessing.extractor import ListingExtractor, to_embedding_text

log = structlog.get_logger(__name__)


class PreprocessingPipeline:
    def __init__(self, extractor: ListingExtractor | None = None) -> None:
        self.extractor = extractor or ListingExtractor()

    async def process_raw_chunks(
        self,
        *,
        session: AsyncSession,
        raw_chunks: Sequence[RawMessageChunk],
    ) -> tuple[int, int]:
        extracted_count = 0
        failed_count = 0

        for chunk in raw_chunks:
            listing = PropertyListing(
                raw_chunk_id=chunk.id,
                sender=chunk.sender,
                timestamp=chunk.message_start,
                status=ListingStatus.PENDING,
            )
            session.add(listing)
            await session.flush()

            extracted, raw_output = await self.extractor.extract(chunk.cleaned_text or chunk.raw_text)
            listing.raw_llm_output = raw_output

            if extracted is None:
                listing.status = ListingStatus.FAILED
                chunk.status = RawMessageChunkStatus.ERROR
                failed_count += 1
                continue

            listing.property_type = extracted.property_type
            listing.bhk = extracted.bhk
            listing.price = extracted.price
            listing.location = extracted.location
            listing.contact_number = extracted.contact_number
            listing.furnished = extracted.furnished
            listing.floor_number = extracted.floor_number
            listing.total_floors = extracted.total_floors
            listing.area_sqft = extracted.area_sqft
            listing.landmark = extracted.landmark
            listing.is_verified = extracted.is_verified
            listing.confidence_score = extracted.confidence_score
            listing.status = ListingStatus.EXTRACTED

            chunk.status = RawMessageChunkStatus.PROCESSED
            embedding_text = to_embedding_text(extracted, chunk.cleaned_text or chunk.raw_text)
            session.add(ListingChunk(listing_id=listing.id, chunk_index=0, content=embedding_text))
            extracted_count += 1

        await session.commit()
        return extracted_count, failed_count


async def load_new_chunks_for_rawfile(session: AsyncSession, rawfile_id: UUID) -> list[RawMessageChunk]:
    stmt = select(RawMessageChunk).where(
        RawMessageChunk.rawfile_id == rawfile_id,
        RawMessageChunk.status == RawMessageChunkStatus.NEW,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
