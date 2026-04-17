from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.core.config import get_settings
from backend.src.models.ingestion import RawFile, RawFileStatus
from backend.src.tasks.ingestion import ingest_raw_file_task

router = APIRouter(prefix="/ingest", tags=["ingestion"])
log = structlog.get_logger(__name__)
settings = get_settings()
UPLOAD_ROOT = Path("/tmp/threadsense_uploads")


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def ingest_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".zip", ".rar"}:
        raise HTTPException(status_code=400, detail="Only .txt, .zip, .rar files are supported")

    payload = await file.read()
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
        return {"task_id": "", "rawfile_id": str(existing_id), "status": "ALREADY_EXISTS"}

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_ROOT / f"{uuid.uuid4()}_{Path(filename).name}"
    stored_path.write_bytes(payload)

    content = ""
    if suffix == ".txt":
        content = payload.decode("utf-8", errors="replace")

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

    task = await ingest_raw_file_task.kiq(str(rawfile.id))
    rawfile.notes = f"{rawfile.notes or ''}; task_id={task.task_id}".strip("; ")
    session.add(rawfile)
    await session.commit()
    log.info("ingest_queued", rawfile_id=str(rawfile.id), task_id=task.task_id)
    return {"task_id": task.task_id, "rawfile_id": str(rawfile.id), "status": "QUEUED"}


@router.get("/status/{task_id}")
async def ingest_status(task_id: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    row = await session.execute(
        select(RawFile).where(RawFile.notes.like(f"%task_id={task_id}%")).order_by(RawFile.uploaded_at.desc())
    )
    rawfile: RawFile | None = row.scalars().first()
    if rawfile is None:
        return {"task_id": task_id, "status": "PENDING", "result": None}

    status_map: dict[str, str] = {
        str(RawFileStatus.PENDING): "PENDING",
        str(RawFileStatus.PROCESSING): "PROCESSING",
        str(RawFileStatus.COMPLETED): "COMPLETED",
        str(RawFileStatus.FAILED): "FAILED",
        str(RawFileStatus.CANCELLED): "FAILED",
    }
    normalized_status: str = status_map.get(str(rawfile.status), str(rawfile.status))

    payload: dict[str, object] = {
        "task_id": task_id,
        "status": normalized_status,
        "result": {
            "rawfile_id": str(rawfile.id),
            "processed": bool(rawfile.processed),
            "dedupe_stats": rawfile.dedupe_stats or {},
            "notes": rawfile.notes,
        },
    }
    if normalized_status == "FAILED":
        payload["error"] = rawfile.notes or "Ingestion failed."
    return payload
