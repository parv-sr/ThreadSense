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

        message_texts = [(chunk.cleaned_text or chunk.raw_text) for chunk in raw_chunks]
        batch_results = await self.extractor.extract_many(message_texts)

        for chunk, (extracted, raw_output) in zip(raw_chunks, batch_results):

            if extracted is None:
                log.warning(
                    "preprocess_extract_failed",
                    chunk_id=str(chunk.id),
                    rawfile_id=str(chunk.rawfile_id),
                    llm_output_preview=(raw_output or "")[:500],
                )
                chunk.status = RawMessageChunkStatus.ERROR
                failed_count += 1
                continue

            listing = PropertyListing(
                raw_chunk_id=chunk.id,
                sender=chunk.sender,
                timestamp=chunk.message_start,
                status=ListingStatus.PENDING,
                raw_llm_output=raw_output,
            )
            session.add(listing)
            await session.flush()

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
