from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawFile, RawFileStatus
from backend.src.preprocessing.pipeline import PreprocessingPipeline, load_new_chunks_for_rawfile
from backend.src.tasks import broker

log = structlog.get_logger(__name__)


@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=10,
    use_delay_exponent=True,
    max_delay_exponent=120,
)
async def preprocess_rawfile_task(rawfile_id: str) -> dict[str, int | str]:
    log.info("preprocess_task_started", rawfile_id=rawfile_id)
    try:
        parsed_id: UUID = UUID(rawfile_id)
    except ValueError as exc:
        return {"status": "FAILED", "error": f"Invalid rawfile_id: {exc}"}

    extracted_count: int = 0
    failed_count: int = 0
    outcome_status: RawFileStatus = RawFileStatus.FAILED
    task_error: Exception | None = None

    async with AsyncSessionLocal() as session:
        rawfile: RawFile | None = await session.get(RawFile, parsed_id)
        if rawfile is None:
            return {"status": "FAILED", "error": "RawFile not found"}

        rawfile.status = RawFileStatus.PROCESSING
        rawfile.progress_percentage = 55
        rawfile.process_started_at = rawfile.process_started_at or datetime.now(timezone.utc)
        await session.commit()
        log.info("preprocess_rawfile_marked_processing", rawfile_id=rawfile_id)

    pipeline: PreprocessingPipeline = PreprocessingPipeline()

    try:
        async with AsyncSessionLocal() as session:
            chunks = await load_new_chunks_for_rawfile(session, parsed_id)
            if not chunks:
                outcome_status = RawFileStatus.COMPLETED
                log.info("preprocess_no_new_chunks", rawfile_id=rawfile_id)
                return {
                    "status": "COMPLETED",
                    "rawfile_id": rawfile_id,
                    "extracted": 0,
                    "failed": 0,
                }

            # Update progress after chunks loaded
            async with AsyncSessionLocal() as update_session:
                rf = await update_session.get(RawFile, parsed_id)
                if rf:
                    rf.progress_percentage = 65
                    await update_session.commit()

            extracted_count, failed_count = await pipeline.process_raw_chunks(session=session, raw_chunks=chunks)
            outcome_status = RawFileStatus.COMPLETED

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

    except Exception as exc:  # noqa: BLE001
        task_error = exc
        # Keep retriable failures visible to workers and never leave PROCESSING behind.
        outcome_status = RawFileStatus.PENDING
        raise

    finally:
        await pipeline.embedding_service.close()
        log.info("preprocess_embedding_service_closed", rawfile_id=rawfile_id)
        # Safety net for worker interruptions/retries: reset lingering PROCESSING rows.
        async with AsyncSessionLocal() as cleanup_session:
            cleanup_rawfile: RawFile | None = await cleanup_session.get(RawFile, parsed_id)
            if cleanup_rawfile is not None and cleanup_rawfile.status in (
                RawFileStatus.PROCESSING, RawFileStatus.PENDING
            ):
                # If task_error exists and we're on final retry, mark FAILED
                if task_error is not None and outcome_status != RawFileStatus.COMPLETED:
                    cleanup_rawfile.status = RawFileStatus.FAILED
                    cleanup_rawfile.notes = f"Preprocessing failed: {task_error}"
                elif outcome_status == RawFileStatus.COMPLETED:
                    cleanup_rawfile.status = RawFileStatus.COMPLETED
                    cleanup_rawfile.progress_percentage = 100
                cleanup_rawfile.process_finished_at = datetime.now(timezone.utc)
                cleanup_rawfile.processed = (cleanup_rawfile.status == RawFileStatus.COMPLETED)
                await cleanup_session.commit()
                log.info(
                    "preprocess_cleanup_status_applied",
                    rawfile_id=rawfile_id,
                    outcome_status=str(cleanup_rawfile.status),
                    has_error=task_error is not None,
                )
