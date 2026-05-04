from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_, select

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawFile, RawFileStatus, RawMessageChunk, RawMessageChunkStatus
from backend.src.models.preprocessing import ListingChunk, ListingStatus, PropertyListing

log = structlog.get_logger(__name__)

# A task is considered stuck/orphaned if it has been in PROCESSING state
# for longer than this threshold with no heartbeat update.
STUCK_THRESHOLD_MINUTES = 15


async def recover_orphaned_tasks() -> None:
    """
    Called once on application startup.

    Scans for three categories of orphaned work and re-enqueues them:
    1. RawFiles stuck in PROCESSING (worker died during ingestion)
    2. RawFiles COMPLETED but with NEW chunks (worker died during preprocessing)
    3. PropertyListings EXTRACTED but with chunks missing embeddings
    """
    from backend.src.tasks.ingestion import ingest_raw_file_task
    from backend.src.preprocessing.tasks import preprocess_rawfile_task
    from backend.src.embeddings.tasks import embed_property_listing_task

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)

    async with AsyncSessionLocal() as session:
        # ── 1. Files stuck in PROCESSING ──────────────────────────────────
        stuck_stmt = select(RawFile).where(
            RawFile.status == RawFileStatus.PROCESSING,
            or_(
                RawFile.last_heartbeat_at.is_(None),
                RawFile.last_heartbeat_at < cutoff,
            ),
        )
        stuck_files = (await session.execute(stuck_stmt)).scalars().all()

        for rawfile in stuck_files:
            rawfile.status = RawFileStatus.PENDING
            rawfile.progress_percentage = 0
            rawfile.process_started_at = None
            rawfile.last_heartbeat_at = None
            rawfile.notes = (rawfile.notes or "") + "; recovered_from_stuck_processing"

        await session.commit()

        for rawfile in stuck_files:
            try:
                await ingest_raw_file_task.kiq(str(rawfile.id))
            except Exception as exc:
                log.error("recovery_requeue_failed", rawfile_id=str(rawfile.id), error=str(exc))

        # ── 2. COMPLETED files with unprocessed chunks ────────────────────
        new_chunks_subq = (
            select(RawMessageChunk.rawfile_id)
            .where(RawMessageChunk.status == RawMessageChunkStatus.NEW)
            .distinct()
            .subquery()
        )
        orphaned_files = (await session.execute(
            select(RawFile).where(
                RawFile.id.in_(select(new_chunks_subq.c.rawfile_id)),
                RawFile.status == RawFileStatus.COMPLETED,
            )
        )).scalars().all()

        for rawfile in orphaned_files:
            try:
                await preprocess_rawfile_task.kiq(str(rawfile.id))
            except Exception as exc:
                log.error("recovery_requeue_failed", rawfile_id=str(rawfile.id), error=str(exc))

        # ── 3. Listings missing embeddings ────────────────────────────────
        unembedded_listings = (await session.execute(
            select(PropertyListing)
            .join(ListingChunk, ListingChunk.property_listing_id == PropertyListing.id)
            .where(
                PropertyListing.status == ListingStatus.EXTRACTED,
                ListingChunk.embedding.is_(None),
            )
            .distinct()
        )).scalars().all()

        for listing in unembedded_listings:
            try:
                await embed_property_listing_task.kiq(str(listing.id))
            except Exception as exc:
                log.error("recovery_requeue_failed", listing_id=str(listing.id), error=str(exc))

    log.info(
        "orphan_recovery_done",
        stuck_files=len(stuck_files),
        orphaned_preprocessing=len(orphaned_files),
        orphaned_embeddings=len(unembedded_listings),
    )
