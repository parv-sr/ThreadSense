from __future__ import annotations

from uuid import UUID

import structlog

from backend.src.db.session import AsyncSessionLocal
from backend.src.embeddings.tasks import embed_property_listing_task
from backend.src.preprocessing.pipeline import PreprocessingPipeline, load_new_chunks_for_rawfile
from backend.src.tasks import broker

log = structlog.get_logger(__name__)


@broker.task
async def preprocess_rawfile_task(rawfile_id: str) -> dict[str, int | str]:
    try:
        parsed_id = UUID(rawfile_id)
    except ValueError as exc:
        return {"status": "FAILED", "error": f"Invalid rawfile_id: {exc}"}

    pipeline = PreprocessingPipeline()

    async with AsyncSessionLocal() as session:
        chunks = await load_new_chunks_for_rawfile(session, parsed_id)
        if not chunks:
            return {"status": "COMPLETED", "rawfile_id": rawfile_id, "extracted": 0, "failed": 0}

        extracted_count, failed_count = await pipeline.process_raw_chunks(session=session, raw_chunks=chunks)

    # Trigger per-listing embedding after preprocessing success.
    if extracted_count > 0:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from backend.src.models.preprocessing import ListingStatus, PropertyListing

            stmt = select(PropertyListing.id).where(
                PropertyListing.status == ListingStatus.EXTRACTED,
                PropertyListing.raw_chunk_id.in_([chunk.id for chunk in chunks]),
            )
            listing_ids = [row[0] for row in (await session.execute(stmt)).all()]

        for listing_id in listing_ids:
            await embed_property_listing_task.kiq(str(listing_id))

    log.info(
        "preprocess_rawfile_done",
        rawfile_id=rawfile_id,
        extracted=extracted_count,
        failed=failed_count,
    )
    return {
        "status": "COMPLETED",
        "rawfile_id": rawfile_id,
        "extracted": extracted_count,
        "failed": failed_count,
    }
