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
    FurnishedType,
    ListingIntent,
    ListingChunk,
    ListingStatus,
    PropertyListing,
    PropertyType,
    TransactionType,
)
from backend.src.preprocessing.extractor import ListingExtractor, ListingExtractionResult, to_embedding_text

logger = structlog.get_logger(__name__)
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

        logger.info("preprocess_batch_start", chunk_count=len(raw_chunks), llm_batch_size=settings.llm_batch_size)

        # v1 -> v2 improvement: chunk-level async extraction in batches via abatch,
        # so we avoid the previous one-LLM-call-per-await bottleneck.
        batch_size: int = max(1, settings.llm_batch_size)
        for start_index in range(0, len(raw_chunks), batch_size):
            batch_chunks: Sequence[RawMessageChunk] = raw_chunks[start_index : start_index + batch_size]
            extractor_inputs: list[tuple[UUID, str]] = [
                (chunk.id, chunk.cleaned_text or chunk.raw_text)
                for chunk in batch_chunks
            ]

            extracted_rows, raw_outputs = await self.extractor.aextract_batch(extractor_inputs)
            result_by_id: dict[UUID, ListingExtractionResult | None] = {
                chunk_id: result for chunk_id, result in extracted_rows
            }

            for chunk in batch_chunks:
                result: ListingExtractionResult | None = result_by_id.get(chunk.id)
                raw_output: str | None = raw_outputs.get(str(chunk.id))

                if result is None:
                    logger.warning(
                        "preprocess_extract_failed",
                        chunk_id=str(chunk.id),
                        rawfile_id=str(chunk.rawfile_id),
                        llm_output_preview=(raw_output or "")[:500],
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
                            location=result.location,
                            contact_number=result.contact_number,
                            furnished=FurnishedType(result.furnished.value)
                            if result.furnished is not None
                            else None,
                            floor_number=result.floor_number,
                            total_floors=result.total_floors,
                            area_sqft=result.area_sqft,
                            landmark=result.landmark,
                            is_verified=result.is_verified,
                            confidence_score=result.confidence_score,
                        )
                        session.add(listing)
                        await session.flush()

                        chunk.status = RawMessageChunkStatus.PROCESSED
                        embedding_text: str = to_embedding_text(result, chunk.cleaned_text or chunk.raw_text)
                        listing_chunk: ListingChunk = ListingChunk(
                            listing_id=listing.id,
                            chunk_index=0,
                            content=embedding_text,
                        )
                        session.add(listing_chunk)
                        await session.flush()

                        # Atomic embedding+upsert in the same task/session for this listing.
                        await self.embedding_service.embed_and_upsert_listing(listing=listing, session=session)

                        extracted_count += 1

                except SQLAlchemyError as db_err:
                    logger.error("database_insert_failed", chunk_id=str(chunk.id), error=str(db_err))
                    chunk.status = RawMessageChunkStatus.ERROR
                    failed_count += 1
                    continue
                except Exception as exc:  # noqa: BLE001
                    logger.error("chunk_processing_failed", chunk_id=str(chunk.id), error=str(exc))
                    chunk.status = RawMessageChunkStatus.ERROR
                    failed_count += 1
                    continue

        # Final commit only includes successful savepoints.
        await session.commit()
        return extracted_count, failed_count


async def load_new_chunks_for_rawfile(session: AsyncSession, rawfile_id: UUID) -> list[RawMessageChunk]:
    stmt = select(RawMessageChunk).where(
        RawMessageChunk.rawfile_id == rawfile_id,
        RawMessageChunk.status == RawMessageChunkStatus.NEW,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
