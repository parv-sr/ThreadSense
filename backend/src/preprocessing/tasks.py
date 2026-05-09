from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawFile, RawFileStatus
from backend.src.preprocessing.pipeline import PreprocessingPipeline, load_new_chunks_for_rawfile
from backend.src.tasks import broker

log = structlog.get_logger(__name__)


async def _heartbeat_rawfile(rawfile_id_: UUID) -> None:
    """Update last_heartbeat_at to signal the task is still alive."""
    async with AsyncSessionLocal() as _session:
        rf = await _session.get(RawFile, rawfile_id_)
        if rf is not None:
            rf.last_heartbeat_at = datetime.now(timezone.utc)
            await _session.commit()


@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=10,
    use_delay_exponent=True,
    max_delay_exponent=120,
)
async def preprocess_rawfile_task(rawfile_id: str) -> dict[str, int | str]:
    _log = log.bind(rawfile_id=rawfile_id)
    _log.info("preprocessing_started")

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
        rawfile.last_heartbeat_at = datetime.now(timezone.utc)
        await session.commit()

    await _heartbeat_rawfile(parsed_id)

    pipeline: PreprocessingPipeline = PreprocessingPipeline()

    try:
        async with AsyncSessionLocal() as session:
            chunks = await load_new_chunks_for_rawfile(session, parsed_id)
            if not chunks:
                outcome_status = RawFileStatus.COMPLETED
                _log.info("preprocessing_completed", result="no_new_chunks")
                return {
                    "status": "COMPLETED",
                    "rawfile_id": rawfile_id,
                    "extracted": 0,
                    "failed": 0,
                }

            _log.info("preprocessing_chunks_loaded", chunk_count=len(chunks))
            await _heartbeat_rawfile(parsed_id)

            # Update progress
            async with AsyncSessionLocal() as update_session:
                rf = await update_session.get(RawFile, parsed_id)
                if rf:
                    rf.progress_percentage = 65
                    await update_session.commit()

            extracted_count, failed_count = await pipeline.process_raw_chunks(session=session, raw_chunks=chunks)
            outcome_status = RawFileStatus.COMPLETED

        _log.info(
            "preprocessing_completed",
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
        outcome_status = RawFileStatus.PENDING
        raise

    finally:
        await pipeline.embedding_service.close()
        # Safety net: reset lingering PROCESSING rows.
        async with AsyncSessionLocal() as cleanup_session:
            cleanup_rawfile: RawFile | None = await cleanup_session.get(RawFile, parsed_id)
            if cleanup_rawfile is not None and cleanup_rawfile.status in (
                RawFileStatus.PROCESSING, RawFileStatus.PENDING
            ):
                if task_error is not None and outcome_status != RawFileStatus.COMPLETED:
                    cleanup_rawfile.status = RawFileStatus.FAILED
                    cleanup_rawfile.notes = f"Preprocessing failed: {task_error}"
                elif outcome_status == RawFileStatus.COMPLETED:
                    cleanup_rawfile.status = RawFileStatus.COMPLETED
                    cleanup_rawfile.progress_percentage = 100
                cleanup_rawfile.process_finished_at = datetime.now(timezone.utc)
                cleanup_rawfile.processed = (cleanup_rawfile.status == RawFileStatus.COMPLETED)
                await cleanup_session.commit()
                _log.info(
                    "preprocessing_cleanup",
                    final_status=str(cleanup_rawfile.status),
                    had_error=task_error is not None,
                )
