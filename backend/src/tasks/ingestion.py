from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import Select, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawFile, RawFileStatus, RawMessageChunk
from backend.src.tasks import broker

log = structlog.get_logger(__name__)

KEYWORDS_RE = re.compile(
    r"(bhk|rent|sale|lease|price|cr\b|lacs?|sqft|carpet|furnished|office|shop|flat|buy|sell|want)",
    re.IGNORECASE,
)
JUNK_RE = re.compile(
    r"(security code changed|waiting for this message|message was deleted|encrypted|joined|left|added|null|media omitted)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class DedupeStats:
    total_messages: int = 0
    system_filtered: int = 0
    media_count: int = 0
    keyword_filtered: int = 0
    local_duplicates: int = 0
    batch_duplicates: int = 0
    db_duplicates: int = 0
    duplicates_removed: int = 0
    final_unique_chunks: int = 0
    created_chunks: int = 0
    ignored_chunks: int = 0
    parser_failures: int = 0
    notes: list[str] = field(default_factory=list)

    def add_note(self, note: str) -> None:
        self.notes.append(note)

    def finalize(self) -> None:
        self.duplicates_removed = self.local_duplicates + self.batch_duplicates + self.db_duplicates


class IngestionError(Exception):
    pass


def _normalize_for_hash(text: str | None, sender: str | None) -> str:
    norm_text = re.sub(r"\s+", "", text or "").lower()
    norm_sender = re.sub(r"\s+", "", sender or "").lower()
    return hashlib.sha256(f"{norm_text}|{norm_sender}".encode("utf-8")).hexdigest()


async def _existing_hashes_stmt(owner_id: uuid.UUID | None) -> Select[tuple[str, str | None]]:
    stmt = (
        select(RawMessageChunk.cleaned_text, RawMessageChunk.sender)
        .join(RawFile, RawFile.id == RawMessageChunk.rawfile_id)
        .where(RawMessageChunk.cleaned_text.is_not(None))
    )
    if owner_id:
        stmt = stmt.where(RawFile.owner_id == owner_id)
    return stmt


@broker.task
async def ingest_raw_file_task(rawfile_id: str) -> dict[str, Any]:
    stats = DedupeStats()
    started_at = datetime.now(timezone.utc)

    try:
        parsed_rawfile_id = uuid.UUID(rawfile_id)
    except ValueError as exc:
        return {"status": "FAILED", "error": f"Invalid rawfile_id: {exc}", "stats": asdict(stats)}

    async with AsyncSessionLocal() as session:
        rawfile = await session.get(RawFile, parsed_rawfile_id)
        if rawfile is None:
            return {"status": "FAILED", "error": "RawFile not found", "stats": asdict(stats)}

        try:
            rawfile.status = RawFileStatus.PROCESSING
            rawfile.process_started_at = started_at
            await session.commit()

            content = rawfile.content or ""
            if not content.strip() and rawfile.file:
                try:
                    content = Path(rawfile.file).read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = Path(rawfile.file).read_text(encoding="cp1252")
                except Exception as exc:  # noqa: BLE001
                    raise IngestionError(f"Unable to read source file: {exc}") from exc

            if not content.strip():
                stats.add_note("Empty upload")
                rawfile.status = RawFileStatus.COMPLETED
                rawfile.processed = True
                rawfile.process_finished_at = datetime.now(timezone.utc)
                rawfile.notes = "No valid messages."
                rawfile.dedupe_stats = asdict(stats)
                await session.commit()
                return {"status": "COMPLETED", "rawfile_id": rawfile_id, "stats": asdict(stats)}

            try:
                import whatsapp_parser  # type: ignore
            except Exception as exc:  # noqa: BLE001
                raise IngestionError(f"Rust parser import failed: {exc}") from exc

            try:
                suffix = Path(rawfile.file_name).suffix.lower()
                if suffix in {".zip", ".rar"}:
                    parsed_rows = whatsapp_parser.parse_zip(rawfile.file)
                elif suffix == ".txt" and rawfile.file:
                    parsed_rows = whatsapp_parser.parse_file(rawfile.file)
                else:
                    parsed_rows = whatsapp_parser.parse_text(content)
            except Exception as exc:  # noqa: BLE001
                raise IngestionError(f"Rust parser failed: {exc}") from exc

            stats.total_messages = len(parsed_rows)

            # 1) in-chat dedupe and parser/system filtering
            local_seen: set[str] = set()
            stage_one: list[dict[str, Any]] = []
            for row in parsed_rows:
                status = getattr(row, "status", "NEW")
                cleaned_text = (getattr(row, "cleaned_text", None) or "").strip()
                raw_text = (getattr(row, "raw_text", "") or "").strip()
                sender = getattr(row, "sender", None)
                message_start = getattr(row, "message_start", None)

                if status == "IGNORED":
                    stats.system_filtered += 1
                    if "media omitted" in raw_text.lower() or "media omitted" in cleaned_text.lower():
                        stats.media_count += 1
                    stats.ignored_chunks += 1
                    continue

                if not cleaned_text:
                    stats.system_filtered += 1
                    stats.ignored_chunks += 1
                    continue

                if JUNK_RE.search(cleaned_text):
                    stats.system_filtered += 1
                    stats.ignored_chunks += 1
                    continue

                if not KEYWORDS_RE.search(cleaned_text):
                    stats.keyword_filtered += 1
                    stats.ignored_chunks += 1
                    continue

                dedupe_hash = _normalize_for_hash(cleaned_text, sender)
                if dedupe_hash in local_seen or status == "DUPLICATE_LOCAL":
                    stats.local_duplicates += 1
                    stats.ignored_chunks += 1
                    continue
                local_seen.add(dedupe_hash)

                stage_one.append(
                    {
                        "sender": sender,
                        "message_start": message_start,
                        "raw_text": raw_text[:10000],
                        "cleaned_text": cleaned_text[:10000],
                        "dedupe_hash": dedupe_hash,
                    }
                )

            # 2) in-batch dedupe
            batch_seen: set[str] = set()
            stage_two: list[dict[str, Any]] = []
            for item in stage_one:
                if item["dedupe_hash"] in batch_seen:
                    stats.batch_duplicates += 1
                    stats.ignored_chunks += 1
                    continue
                batch_seen.add(item["dedupe_hash"])
                stage_two.append(item)

            # 3) in-db dedupe
            existing_hashes: set[str] = set()
            stmt = await _existing_hashes_stmt(rawfile.owner_id)
            for cleaned_text, sender in (await session.execute(stmt)).all():
                existing_hashes.add(_normalize_for_hash(cleaned_text or "", sender))

            final_rows: list[RawMessageChunk] = []
            for item in stage_two:
                if item["dedupe_hash"] in existing_hashes:
                    stats.db_duplicates += 1
                    stats.ignored_chunks += 1
                    continue

                parsed_dt = None
                if item["message_start"]:
                    try:
                        parsed_dt = datetime.fromisoformat(item["message_start"].replace("Z", "+00:00"))
                    except ValueError:
                        parsed_dt = None

                final_rows.append(
                    RawMessageChunk(
                        rawfile_id=rawfile.id,
                        message_start=parsed_dt,
                        sender=item["sender"],
                        raw_text=item["raw_text"],
                        cleaned_text=item["cleaned_text"],
                        split_into=0,
                        status="NEW",
                        user_id=rawfile.owner_id,
                    )
                )

            if final_rows:
                session.add_all(final_rows)

            stats.created_chunks = len(final_rows)
            stats.final_unique_chunks = len(final_rows)
            stats.finalize()

            rawfile.status = RawFileStatus.COMPLETED
            rawfile.processed = True
            rawfile.process_finished_at = datetime.now(timezone.utc)
            rawfile.notes = f"Processed {stats.total_messages} messages"
            rawfile.dedupe_stats = asdict(stats)

            await session.commit()
            log.info(
                "ingestion_completed",
                rawfile_id=str(rawfile.id),
                created=stats.created_chunks,
                ignored=stats.ignored_chunks,
            )

            # ---------------------------------------------------------------
            # Phase 2: Chain the extraction + embedding worker
            # ---------------------------------------------------------------
            if stats.created_chunks > 0:
                from backend.src.tasks.extraction import extract_and_embed_task  # noqa: PLC0415

                try:
                    await extract_and_embed_task.kiq(str(rawfile.id))
                    log.info("extract_embed_enqueued", rawfile_id=str(rawfile.id))
                except Exception as chain_exc:  # noqa: BLE001
                    # Non-fatal — ingestion succeeded; extraction can be retried manually
                    log.warning(
                        "extract_embed_enqueue_failed",
                        rawfile_id=str(rawfile.id),
                        error=str(chain_exc),
                    )

            return {
                "status": "COMPLETED",
                "rawfile_id": str(rawfile.id),
                "created": stats.created_chunks,
                "ignored": stats.ignored_chunks,
                "stats": asdict(stats),
            }

        except (IntegrityError, DBAPIError) as exc:
            await session.rollback()
            stats.parser_failures += 1
            rawfile.status = RawFileStatus.FAILED
            rawfile.process_finished_at = datetime.now(timezone.utc)
            rawfile.notes = f"Database failure: {exc}"
            rawfile.dedupe_stats = asdict(stats)
            await session.commit()
            log.exception("ingestion_db_failure", rawfile_id=str(rawfile.id))
            return {"status": "FAILED", "error": str(exc), "stats": asdict(stats)}
        except IngestionError as exc:
            await session.rollback()
            stats.parser_failures += 1
            rawfile.status = RawFileStatus.FAILED
            rawfile.process_finished_at = datetime.now(timezone.utc)
            rawfile.notes = str(exc)
            rawfile.dedupe_stats = asdict(stats)
            await session.commit()
            log.exception("ingestion_parser_failure", rawfile_id=str(rawfile.id), error=str(exc))
            return {"status": "FAILED", "error": str(exc), "stats": asdict(stats)}
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            stats.parser_failures += 1
            rawfile.status = RawFileStatus.FAILED
            rawfile.process_finished_at = datetime.now(timezone.utc)
            rawfile.notes = f"Unhandled pipeline error: {exc}"
            rawfile.dedupe_stats = asdict(stats)
            await session.commit()
            log.exception("ingestion_unhandled_failure", rawfile_id=str(rawfile.id))
            return {"status": "FAILED", "error": str(exc), "stats": asdict(stats)}