from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.core.config import get_settings
from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawFile, RawFileStatus, RawMessageChunk, RawMessageChunkStatus
from backend.src.models.preprocessing import PropertyListing
from backend.src.tasks.ingestion import ingest_raw_file_task

def _sanitise_content(text: str) -> str:
    """Remove null bytes (\x00) that PostgreSQL refuses in TEXT/VARCHAR columns.
    We already use errors='replace' on decode, but some WhatsApp exports
    (especially testdata2.txt) still contain literal \x00."""
    if not text:
        return ""
    return text.replace("\x00", "")

router = APIRouter(prefix="/ingest", tags=["ingestion"])
log = structlog.get_logger(__name__)
settings = get_settings()
UPLOAD_ROOT = Path("/tmp/threadsense_uploads")
TASK_ID_PATTERN = re.compile(r"(?:^|;\s*)task_id=([^;]+)")


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _normalize_status(raw_status: str | RawFileStatus) -> str:
    status_value = str(raw_status)
    status_map: dict[str, str] = {
        str(RawFileStatus.PENDING): "PENDING",
        str(RawFileStatus.PROCESSING): "PROCESSING",
        str(RawFileStatus.COMPLETED): "COMPLETED",
        str(RawFileStatus.FAILED): "FAILED",
        str(RawFileStatus.CANCELLED): "FAILED",
    }
    return status_map.get(status_value, status_value)


def _extract_task_id(notes: str | None) -> str | None:
    if not notes:
        return None
    match = TASK_ID_PATTERN.search(notes)
    return match.group(1).strip() if match else None


def _safe_int(value: object) -> int:
    return int(value or 0)


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _build_progress_payload(
    *,
    rawfile: RawFile,
    total_chunks: int,
    processed_chunks: int,
    failed_chunks: int,
    listings_count: int,
) -> dict[str, object]:
    normalized_status = _normalize_status(rawfile.status)
    terminal = normalized_status in {"COMPLETED", "FAILED"}
    reviewed_chunks = processed_chunks + failed_chunks

    if normalized_status == "COMPLETED":
        percentage = 100
        stage = "Ready"
        message = (
            f"{listings_count} listing{'s' if listings_count != 1 else ''} extracted"
            if listings_count > 0
            else "Processing finished with no extracted listings"
        )
    elif normalized_status == "FAILED":
        percentage = min(95, 12 + reviewed_chunks * 3) if total_chunks > 0 else 18
        stage = "Needs attention"
        message = rawfile.notes or "Processing failed before the file could be fully structured."
    elif total_chunks > 0:
        completion_ratio = min(reviewed_chunks / total_chunks, 1.0)
        percentage = min(96, 42 + round(completion_ratio * 54))
        stage = "Structuring listings"
        message = f"{reviewed_chunks} of {total_chunks} candidate messages processed"
    elif rawfile.process_started_at is not None:
        percentage = 26
        stage = "Parsing conversation"
        message = "Reading the raw conversation export and identifying candidate listings"
    else:
        percentage = 8
        stage = "Queued"
        message = "Upload received and waiting for a worker slot"

    return {
        "status": normalized_status,
        "percentage": percentage,
        "stage": stage,
        "message": message,
        "terminal": terminal,
        "should_poll": not terminal,
        "chunks_total": total_chunks,
        "chunks_processed": processed_chunks,
        "chunks_failed": failed_chunks,
        "listings_extracted": listings_count,
    }


def _summarize_insights(listings: list[dict[str, object]], progress: dict[str, object]) -> dict[str, object]:
    listing_count = len(listings)
    stage = str(progress["stage"])
    percentage = int(progress["percentage"])

    if listing_count == 0 and not bool(progress["terminal"]):
        return {
            "headline": "Inference is warming up",
            "subheadline": f"{stage} is underway. Structured listings will appear here as the pipeline advances.",
            "highlights": [
                f"Current stage: {stage}",
                f"Pipeline progress: {percentage}%",
            ],
            "status_summary": str(progress["message"]),
        }

    if listing_count == 0:
        return {
            "headline": "No structured listings extracted",
            "subheadline": "The upload completed, but none of the messages matched the current listing extraction criteria.",
            "highlights": [
                "Try another export with richer property messages",
                "Review deduplication notes for clues about ignored content",
            ],
            "status_summary": str(progress["message"]),
        }

    locations = Counter(
        str(item["location"]).strip()
        for item in listings
        if item.get("location")
    )
    intents = Counter(str(item["listingIntent"]) for item in listings)
    avg_confidence = sum(float(item["confidenceScore"]) for item in listings) / listing_count
    highlights: list[str] = [
        f"{listing_count} listing{'s' if listing_count != 1 else ''} extracted so far",
        f"Average confidence {avg_confidence * 100:.0f}%",
    ]
    if locations:
        top_location, top_location_count = locations.most_common(1)[0]
        highlights.append(
            f"Most active locality: {top_location} ({top_location_count} listing{'s' if top_location_count != 1 else ''})"
        )
    dominant_intent, dominant_intent_count = intents.most_common(1)[0]
    highlights.append(
        f"Dominant intent: {dominant_intent.lower()} ({dominant_intent_count} listing{'s' if dominant_intent_count != 1 else ''})"
    )

    return {
        "headline": f"{listing_count} structured listing{'s' if listing_count != 1 else ''} ready",
        "subheadline": "The extraction pipeline is surfacing normalized property intelligence from the uploaded conversation.",
        "highlights": highlights,
        "status_summary": str(progress["message"]),
    }


async def _fetch_upload_overview(
    session: AsyncSession,
    *,
    rawfile_id: UUID | None = None,
) -> list[dict[str, object]]:
    chunk_stats_subquery = (
        select(
            RawMessageChunk.rawfile_id.label("rawfile_id"),
            func.count(RawMessageChunk.id).label("total_chunks"),
            func.sum(
                case((RawMessageChunk.status == RawMessageChunkStatus.PROCESSED, 1), else_=0)
            ).label("processed_chunks"),
            func.sum(
                case((RawMessageChunk.status == RawMessageChunkStatus.ERROR, 1), else_=0)
            ).label("failed_chunks"),
        )
        .group_by(RawMessageChunk.rawfile_id)
        .subquery()
    )

    listing_stats_subquery = (
        select(
            RawMessageChunk.rawfile_id.label("rawfile_id"),
            func.count(PropertyListing.id).label("listings_count"),
            func.avg(PropertyListing.confidence_score).label("avg_confidence"),
        )
        .join(RawMessageChunk, RawMessageChunk.id == PropertyListing.raw_chunk_id)
        .group_by(RawMessageChunk.rawfile_id)
        .subquery()
    )

    stmt = (
        select(
            RawFile,
            func.coalesce(chunk_stats_subquery.c.total_chunks, 0).label("total_chunks"),
            func.coalesce(chunk_stats_subquery.c.processed_chunks, 0).label("processed_chunks"),
            func.coalesce(chunk_stats_subquery.c.failed_chunks, 0).label("failed_chunks"),
            func.coalesce(listing_stats_subquery.c.listings_count, 0).label("listings_count"),
            listing_stats_subquery.c.avg_confidence.label("avg_confidence"),
        )
        .outerjoin(chunk_stats_subquery, chunk_stats_subquery.c.rawfile_id == RawFile.id)
        .outerjoin(listing_stats_subquery, listing_stats_subquery.c.rawfile_id == RawFile.id)
        .order_by(RawFile.uploaded_at.desc())
    )
    if rawfile_id is not None:
        stmt = stmt.where(RawFile.id == rawfile_id)

    rows = (await session.execute(stmt)).all()
    uploads: list[dict[str, object]] = []
    for rawfile, total_chunks, processed_chunks, failed_chunks, listings_count, avg_confidence in rows:
        total_chunks_value = _safe_int(total_chunks)
        processed_chunks_value = _safe_int(processed_chunks)
        failed_chunks_value = _safe_int(failed_chunks)
        listings_count_value = _safe_int(listings_count)
        progress = _build_progress_payload(
            rawfile=rawfile,
            total_chunks=total_chunks_value,
            processed_chunks=processed_chunks_value,
            failed_chunks=failed_chunks_value,
            listings_count=listings_count_value,
        )
        uploads.append(
            {
                "rawfileId": str(rawfile.id),
                "fileName": rawfile.file_name,
                "status": _normalize_status(rawfile.status),
                "processed": bool(rawfile.processed),
                "uploadedAt": _isoformat(rawfile.uploaded_at),
                "processStartedAt": _isoformat(rawfile.process_started_at),
                "processFinishedAt": _isoformat(rawfile.process_finished_at),
                "notes": rawfile.notes,
                "source": rawfile.source,
                "taskId": _extract_task_id(rawfile.notes),
                "dedupeStats": rawfile.dedupe_stats or {},
                "progress": progress,
                "listingsCount": listings_count_value,
                "averageConfidence": _safe_float(avg_confidence),
            }
        )
    return uploads


async def _fetch_upload_detail_payload(session: AsyncSession, rawfile_id: UUID) -> dict[str, object]:
    uploads = await _fetch_upload_overview(session, rawfile_id=rawfile_id)
    if not uploads:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload = uploads[0]
    listings_stmt = (
        select(
            PropertyListing,
            RawMessageChunk.cleaned_text,
            RawMessageChunk.raw_text,
        )
        .join(RawMessageChunk, RawMessageChunk.id == PropertyListing.raw_chunk_id)
        .where(RawMessageChunk.rawfile_id == rawfile_id)
        .order_by(PropertyListing.timestamp.desc().nullslast(), PropertyListing.created_at.desc())
    )
    listing_rows = (await session.execute(listings_stmt)).all()
    listings: list[dict[str, object]] = []
    for listing, cleaned_text, raw_text in listing_rows:
        excerpt = cleaned_text or raw_text
        listings.append(
            {
                "id": str(listing.id),
                "rawChunkId": str(listing.raw_chunk_id),
                "sender": listing.sender,
                "timestamp": _isoformat(listing.timestamp),
                "propertyType": str(listing.property_type),
                "transactionType": str(listing.transaction_type),
                "listingIntent": str(listing.listing_intent),
                "location": listing.location,
                "price": listing.price,
                "bhk": listing.bhk,
                "areaSqft": listing.area_sqft,
                "furnished": str(listing.furnished) if listing.furnished is not None else None,
                "landmark": listing.landmark,
                "contactNumber": listing.contact_number,
                "isVerified": bool(listing.is_verified),
                "status": str(listing.status),
                "confidenceScore": listing.confidence_score,
                "excerpt": excerpt[:240],
            }
        )

    return {
        "upload": upload,
        "insights": {
            **_summarize_insights(listings, upload["progress"]),
            "listings": listings,
        },
        "streamedAt": datetime.now(timezone.utc).isoformat(),
    }


def _sse_frame(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    log.info("ingest_request_received", filename=filename, suffix=suffix)
    if suffix not in {".txt", ".zip", ".rar"}:
        raise HTTPException(status_code=400, detail="Only .txt, .zip, .rar files are supported")

    payload = await file.read()
    log.info("ingest_payload_loaded", filename=filename, payload_bytes=len(payload))
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(payload) > settings.ingest_max_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds configured size limit")

    text_for_fingerprint = payload.decode("utf-8", errors="replace")
    fingerprint = str(uuid.uuid5(uuid.NAMESPACE_URL, text_for_fingerprint[:10000] + filename.lower()))

    duplicate_q = await session.execute(
        select(RawFile.id).where(
            RawFile.file_name == filename,
            RawFile.processed.is_(True),
            RawFile.notes.like(f"%fingerprint={fingerprint}%"),
        )
    )
    existing_id = duplicate_q.scalar_one_or_none()
    if existing_id:
        log.info("ingest_duplicate_detected", filename=filename, existing_rawfile_id=str(existing_id))
        return {"task_id": "", "rawfile_id": str(existing_id), "status": "ALREADY_EXISTS"}

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_ROOT / f"{uuid.uuid4()}_{Path(filename).name}"
    stored_path.write_bytes(payload)

    content = ""
    if suffix == ".txt":
        content: str = _sanitise_content(
            payload.decode("utf-8", errors="replace")
        )

    rawfile = RawFile(
        file=str(stored_path),
        file_name=filename,
        content=content,
        source="upload",
        processed=False,
        status=RawFileStatus.PENDING,
        owner_id=None,
        notes=f"fingerprint={fingerprint}; uploaded_at={datetime.now(timezone.utc).isoformat()}",
    )
    session.add(rawfile)
    await session.commit()
    await session.refresh(rawfile)
    log.info("ingest_rawfile_created", rawfile_id=str(rawfile.id), stored_path=str(stored_path))

    task = await ingest_raw_file_task.kiq(str(rawfile.id))
    rawfile.notes = f"{rawfile.notes or ''}; task_id={task.task_id}".strip("; ")
    session.add(rawfile)
    await session.commit()
    log.info("ingest_queued", rawfile_id=str(rawfile.id), task_id=task.task_id)
    return {"task_id": task.task_id, "rawfile_id": str(rawfile.id), "status": "QUEUED"}


@router.get("/uploads")
async def list_uploads(session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    uploads = await _fetch_upload_overview(session)
    return {"uploads": uploads}


@router.get("/uploads/{rawfile_id}")
async def upload_detail(rawfile_id: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    try:
        parsed_id = UUID(rawfile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rawfile_id must be a valid UUID") from exc
    return await _fetch_upload_detail_payload(session, parsed_id)


@router.get("/uploads/{rawfile_id}/progress")
async def upload_progress(rawfile_id: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    try:
        parsed_id = UUID(rawfile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rawfile_id must be a valid UUID") from exc

    uploads = await _fetch_upload_overview(session, rawfile_id=parsed_id)
    if not uploads:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload = uploads[0]
    return {
        "rawfileId": upload["rawfileId"],
        "fileName": upload["fileName"],
        "progress": upload["progress"],
    }


@router.get("/uploads/{rawfile_id}/stream")
async def upload_detail_stream(rawfile_id: str, request: Request) -> StreamingResponse:
    try:
        parsed_id = UUID(rawfile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rawfile_id must be a valid UUID") from exc

    async def event_generator() -> asyncio.AsyncIterator[str]:
        previous_payload: str | None = None
        while True:
            if await request.is_disconnected():
                break

            async with AsyncSessionLocal() as session:
                payload = await _fetch_upload_detail_payload(session, parsed_id)

            serialized_payload = json.dumps(payload, separators=(",", ":"))
            if serialized_payload != previous_payload:
                yield _sse_frame("snapshot", payload)
                previous_payload = serialized_payload
            else:
                yield _sse_frame(
                    "heartbeat",
                    {"rawfileId": rawfile_id, "streamedAt": datetime.now(timezone.utc).isoformat()},
                )

            progress = payload["upload"]["progress"]
            if bool(progress["terminal"]):
                yield _sse_frame(
                    "done",
                    {
                        "rawfileId": rawfile_id,
                        "status": progress["status"],
                        "streamedAt": datetime.now(timezone.utc).isoformat(),
                    },
                )
                break

            await asyncio.sleep(2.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{task_id}")
async def ingest_status(task_id: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    log.debug("ingest_status_requested", task_id=task_id)
    row = await session.execute(
        select(RawFile).where(RawFile.notes.like(f"%task_id={task_id}%")).order_by(RawFile.uploaded_at.desc())
    )
    rawfile: RawFile | None = row.scalars().first()
    if rawfile is None:
        log.info("ingest_status_pending", task_id=task_id)
        return {"task_id": task_id, "status": "PENDING", "result": None}

    normalized_status = _normalize_status(rawfile.status)

    payload: dict[str, object] = {
        "task_id": task_id,
        "status": normalized_status,
        "progress_percentage": rawfile.progress_percentage,
        "result": {
            "rawfile_id": str(rawfile.id),
            "processed": bool(rawfile.processed),
            "dedupe_stats": rawfile.dedupe_stats or {},
            "notes": rawfile.notes,
        },
    }
    if normalized_status == "FAILED":
        payload["error"] = rawfile.notes or "Ingestion failed."
    log.info("ingest_status_resolved", task_id=task_id, status=normalized_status, rawfile_id=str(rawfile.id))
    return payload
