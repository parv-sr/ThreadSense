from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.config import get_settings
from backend.src.embeddings.service import EmbeddingService
from backend.src.models.ingestion import RawMessageChunk, RawMessageChunkStatus
from backend.src.models.preprocessing import (
    Furnishing,
    ListingIntent,
    ListingChunk,
    ListingStatus,
    PriceStatus,
    PropertyListing,
    PropertyType,
    TransactionType,
)
from backend.src.preprocessing.extractor import ListingExtractor, ListingExtractionResult, to_embedding_text

log = structlog.get_logger(__name__)
settings = get_settings()


class PreprocessingPipeline:
    def __init__(
        self,
        extractor: ListingExtractor | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.extractor: ListingExtractor = extractor or ListingExtractor()
        self.embedding_service: EmbeddingService = embedding_service or EmbeddingService()

    async def process_raw_chunks(
        self,
        *,
        session: AsyncSession,
        raw_chunks: Sequence[RawMessageChunk],
    ) -> tuple[int, int]:
        extracted_count: int = 0
        failed_count: int = 0
        batch_size: int = max(1, settings.llm_batch_size)

        log.info("extraction_started", total_chunks=len(raw_chunks), batch_size=batch_size)

        for start_index in range(0, len(raw_chunks), batch_size):
            batch_chunks: Sequence[RawMessageChunk] = raw_chunks[start_index : start_index + batch_size]
            extractor_inputs: list[tuple[UUID, str]] = [
                (chunk.id, chunk.cleaned_text or chunk.raw_text)
                for chunk in batch_chunks
            ]

            extracted_rows, raw_outputs = await self.extractor.aextract_batch(extractor_inputs)
            log.info(
                "extraction_batch_done",
                batch_offset=start_index,
                batch_size=len(batch_chunks),
                extracted=len(extracted_rows),
            )
            result_by_id: dict[UUID, ListingExtractionResult | None] = {
                chunk_id: result for chunk_id, result in extracted_rows
            }

            for chunk in batch_chunks:
                result: ListingExtractionResult | None = result_by_id.get(chunk.id)
                raw_output: str | None = raw_outputs.get(str(chunk.id))

                if result is None:
                    log.warning(
                        "extraction_chunk_failed",
                        chunk_id=str(chunk.id),
                        reason=(raw_output or "")[:200],
                    )
                    chunk.status = RawMessageChunkStatus.ERROR
                    failed_count += 1
                    continue

                try:
                    # Savepoint logic: one failing listing never rolls back the full batch.
                    async with session.begin_nested():
                        listing: PropertyListing = PropertyListing(
                            raw_chunk_id=chunk.id,
                            sender=chunk.sender,
                            timestamp=chunk.message_start,
                            status=ListingStatus.EXTRACTED,
                            raw_llm_output=raw_output,
                            property_type=PropertyType(result.property_type.value),
                            transaction_type=TransactionType(result.transaction_type.value)
                            if result.transaction_type is not None
                            else TransactionType.UNKNOWN,
                            listing_intent=ListingIntent(result.listing_intent.value)
                            if result.listing_intent is not None
                            else ListingIntent.UNKNOWN,
                            bhk=result.bhk,
                            price=result.price,
                            price_min=result.price_min or result.price,
                            price_max=result.price_max or result.price,
                            price_status=PriceStatus(result.price_status.value),
                            location=result.location,
                            canonical_location=result.canonical_location,
                            contact_number=result.contact_number,
                            furnishing=Furnishing(result.furnished.value)
                            if result.furnished is not None
                            else None,
                            pets_allowed=result.pets_allowed,
                            suspicious_flags=result.suspicious_flags,
                            floor_number=result.floor_number,
                            total_floors=result.total_floors,
                            sqft=result.area_sqft,
                            landmark=result.landmark,
                            is_verified=result.is_verified,
                            confidence_score=result.confidence_score,
                        )
                        session.add(listing)
                        await session.flush()

                        chunk.status = RawMessageChunkStatus.PROCESSED
                        embedding_text: str = to_embedding_text(result, chunk.cleaned_text or chunk.raw_text)
                        listing_chunk: ListingChunk = ListingChunk(
                            property_listing_id=listing.id,
                            chunk_index=0,
                            content=embedding_text,
                        )
                        session.add(listing_chunk)
                        await session.flush()

                        await self.embedding_service.embed_and_upsert_listing(listing=listing, session=session)
                        extracted_count += 1

                except SQLAlchemyError as db_err:
                    log.error("extraction_db_error", chunk_id=str(chunk.id), error=str(db_err))
                    chunk.status = RawMessageChunkStatus.ERROR
                    failed_count += 1
                    continue
                except Exception as exc:  # noqa: BLE001
                    log.error("extraction_chunk_error", chunk_id=str(chunk.id), error=str(exc))
                    chunk.status = RawMessageChunkStatus.ERROR
                    failed_count += 1
                    continue

        await session.commit()
        log.info("extraction_completed", extracted=extracted_count, failed=failed_count)
        return extracted_count, failed_count


async def load_new_chunks_for_rawfile(session: AsyncSession, rawfile_id: UUID) -> list[RawMessageChunk]:
    stmt = select(RawMessageChunk).where(
        RawMessageChunk.rawfile_id == rawfile_id,
        RawMessageChunk.status == RawMessageChunkStatus.NEW,
    )
    result = await session.execute(stmt)
    chunks: list[RawMessageChunk] = list(result.scalars().all())
    return chunks
