from __future__ import annotations

import asyncio
import uuid
from typing import Any, List, Optional, Literal
from uuid import UUID

import structlog
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from qdrant_client import AsyncQdrantClient, models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.ingestion import RawMessageChunk, RawMessageChunkStatus
from backend.src.tasks import broker
from backend.src.core.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

# --- Constants ---
BATCH_SIZE = 50
QDRANT_COLLECTION = "threadsense_listings"


# ---------------------------------------------------------------------------
# Pydantic schema mirrors apps/preprocessing/extractor.py's PropertyListing
# ---------------------------------------------------------------------------

class ExtractedListing(BaseModel):
    """Structured output extracted from a single WhatsApp property message."""

    cleaned_text: str = Field(
        ...,
        description=(
            "A single, concise sentence summarising the listing. "
            "Remove emojis, agent names, and fluff. "
            "Example: '2 BHK fully furnished flat for rent in Bandra West, price 85k.'"
        ),
    )
    listing_intent: Literal["OFFER", "REQUEST"] = Field(
        default="OFFER",
        description=(
            "'OFFER' is for property owners listing a place. "
            "'REQUEST' is for users looking/wanting a place."
        ),
    )
    transaction_type: Literal["RENT", "SALE"] = Field(
        default="SALE",
        description="'RENT' covers rent/lease. 'SALE' covers buy/sell/ownership.",
    )
    property_type: Literal["RESIDENTIAL", "COMMERCIAL", "PLOT", "LAND", "UNKNOWN"] = Field(
        ..., description="Type of property."
    )
    location: str = Field(
        ...,
        description="Specific locality (e.g., 'Pali Hill', 'BKC'). Do not include 'Mumbai'.",
    )
    building_name: Optional[str] = Field(None, description="Name of the building, project, or society.")
    bhk: Optional[float] = Field(None, description="Number of bedrooms. Use 0.5 for RK/Studio.")
    sqft: Optional[int] = Field(None, description="Carpet area in square feet.")
    price: Optional[int] = Field(
        None, description="Total price or rent in INR. Normalise '1.5 Cr' to 15000000."
    )
    furnishing: Optional[
        Literal[
            "FULLY FURNISHED",
            "FURNISHED",
            "SEMI-FURNISHED",
            "SEMI FURNISHED",
            "UNFURNISHED",
            "UNKNOWN",
        ]
    ] = Field(None)
    parking: Optional[int] = Field(None, description="Number of car parks.")
    features: List[str] = Field(
        default_factory=list,
        description="Key amenities (e.g., 'Sea View', 'Balcony', 'Terrace').",
    )
    contact_numbers: List[str] = Field(
        default_factory=list, description="Extracted phone numbers."
    )

    # --- Validators (mirrors extractor.py) ---

    @field_validator("listing_intent", mode="before")
    @classmethod
    def normalize_listing_intent(cls, v: Any, info: ValidationInfo) -> str:
        cleaned_text = str((info.data or {}).get("cleaned_text") or "").lower()
        if any(term in cleaned_text for term in ["looking for", "want", "require", "need"]):
            return "REQUEST"
        if not v:
            return "OFFER"
        s = str(v).upper().strip()
        if s in {"REQUEST", "REQUIREMENT", "LOOKING"}:
            return "REQUEST"
        return "OFFER"

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, v: Any, info: ValidationInfo) -> str:
        raw = f"{str(v or '')} {str((info.data or {}).get('cleaned_text') or '')}".upper().strip()
        if "LEASE" in raw or "LICENSE" in raw or "RENT" in raw:
            return "RENT"
        if "SALE" in raw or "BUY" in raw or "SELL" in raw or "OWNERSHIP" in raw or "OWN" in raw:
            return "SALE"
        return "SALE"

    @field_validator("location", mode="before")
    @classmethod
    def ensure_location_string(cls, v: Any) -> str:
        if v is None:
            return "Unknown"
        return str(v)

    @field_validator("furnishing", mode="before")
    @classmethod
    def normalize_furnishing(cls, v: Any) -> Optional[str]:
        if not v:
            return None
        s = str(v).upper().strip()
        if "FULLY" in s or s == "FURNISHED":
            return "FURNISHED"
        if "SEMI" in s:
            return "SEMI-FURNISHED"
        if "EMPTY" in s or "NOT" in s or "UNFURNISHED" in s:
            return "UNFURNISHED"
        if s in {"FURNISHED", "SEMI-FURNISHED", "UNFURNISHED"}:
            return s
        return "UNKNOWN"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.qdrant_endpoint,
        api_key=settings.qdrant_api_key,
    )


async def _ensure_collection(client: AsyncQdrantClient, collection: str) -> None:
    """Create the Qdrant collection if it does not exist yet."""
    existing = {c.name for c in (await client.get_collections()).collections}
    if collection not in existing:
        await client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=1536, distance=qmodels.Distance.COSINE),
        )
        log.info("qdrant_collection_created", collection=collection)


async def _extract_single_chunk(
    llm_structured: Any,
    chunk: RawMessageChunk,
) -> Optional[ExtractedListing]:
    """Run structured extraction on one chunk; returns None on failure."""
    text = chunk.cleaned_text or chunk.raw_text
    if not text or not text.strip():
        return None
    try:
        result: ExtractedListing = await llm_structured.ainvoke(
            f"Extract real-estate listing details from this WhatsApp message:\n\n{text[:3000]}"
        )
        return result
    except Exception as exc:
        log.warning(
            "extraction_chunk_failed",
            chunk_id=str(chunk.id),
            error=str(exc),
        )
        return None


async def _process_batch(
    batch: List[RawMessageChunk],
    llm_structured: Any,
    embeddings_model: OpenAIEmbeddings,
    qdrant_client: AsyncQdrantClient,
    session: AsyncSession,
) -> int:
    """Extract, embed, upsert and mark a single batch. Returns number of successes."""

    # 1. Concurrent structured extraction
    extraction_tasks = [_extract_single_chunk(llm_structured, chunk) for chunk in batch]
    extracted: List[Optional[ExtractedListing]] = await asyncio.gather(*extraction_tasks)

    # 2. Pair chunks with successful extractions
    valid_pairs = [
        (chunk, listing)
        for chunk, listing in zip(batch, extracted)
        if listing is not None
    ]
    if not valid_pairs:
        log.warning("batch_no_valid_extractions", batch_size=len(batch))
        return 0

    valid_chunks, valid_listings = zip(*valid_pairs)

    # 3. Embed the cleaned texts asynchronously
    texts_to_embed = [
        listing.cleaned_text for listing in valid_listings
    ]
    try:
        vectors: List[List[float]] = await embeddings_model.aembed_documents(texts_to_embed)
    except Exception as exc:
        log.error("batch_embedding_failed", error=str(exc))
        return 0

    # 4. Build Qdrant points
    points: List[qmodels.PointStruct] = []
    for chunk, listing, vector in zip(valid_chunks, valid_listings, vectors):
        payload: dict[str, Any] = listing.model_dump()
        payload["chunk_id"] = str(chunk.id)
        payload["rawfile_id"] = str(chunk.rawfile_id)
        payload["sender"] = chunk.sender
        payload["message_start"] = (
            chunk.message_start.isoformat() if chunk.message_start else None
        )
        # Numeric price for range filters
        payload["price_numeric"] = float(listing.price) if listing.price else None

        points.append(
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )
        )

    # 5. Upsert into Qdrant
    try:
        await qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        log.info("qdrant_upsert_ok", count=len(points))
    except Exception as exc:
        log.error("qdrant_upsert_failed", error=str(exc))
        return 0

    # 6. Mark chunks as EMBEDDED in Postgres
    succeeded = 0
    for chunk in valid_chunks:
        chunk.status = "EMBEDDED"
        session.add(chunk)
        succeeded += 1

    await session.commit()
    return succeeded


# ---------------------------------------------------------------------------
# Taskiq worker
# ---------------------------------------------------------------------------

@broker.task
async def extract_and_embed_task(rawfile_id: str) -> dict[str, Any]:
    """
    Fetch all NEW chunks for *rawfile_id*, extract structured listing data
    via GPT-4o-mini, embed with OpenAI text-embedding-3-small and upsert
    vectors + payloads into Qdrant.
    """
    import os

    try:
        parsed_id = UUID(rawfile_id)
    except ValueError as exc:
        return {"status": "FAILED", "error": f"Invalid rawfile_id: {exc}"}

    log.info("extract_embed_start", rawfile_id=rawfile_id)

    # --- Build LLM with structured output ---
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    llm_structured = llm.with_structured_output(ExtractedListing)

    embeddings_model = OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    qdrant_client = _build_qdrant_client()

    total_processed = 0
    total_failed = 0

    async with AsyncSessionLocal() as session:
        # Fetch all NEW chunks for this rawfile
        stmt = select(RawMessageChunk).where(
            RawMessageChunk.rawfile_id == parsed_id,
            RawMessageChunk.status == RawMessageChunkStatus.NEW,
        )
        result = await session.execute(stmt)
        chunks: List[RawMessageChunk] = list(result.scalars().all())

    if not chunks:
        log.info("extract_embed_no_chunks", rawfile_id=rawfile_id)
        return {"status": "COMPLETED", "rawfile_id": rawfile_id, "processed": 0}

    log.info("extract_embed_chunks_found", rawfile_id=rawfile_id, count=len(chunks))

    # Ensure Qdrant collection exists
    try:
        await _ensure_collection(qdrant_client, QDRANT_COLLECTION)
    except Exception as exc:
        log.error("qdrant_collection_check_failed", error=str(exc))
        return {"status": "FAILED", "error": str(exc)}

    # Process in batches of BATCH_SIZE
    batches = [chunks[i : i + BATCH_SIZE] for i in range(0, len(chunks), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        log.info(
            "extract_embed_batch",
            rawfile_id=rawfile_id,
            batch=batch_idx + 1,
            total_batches=len(batches),
            size=len(batch),
        )
        try:
            async with AsyncSessionLocal() as session:
                # Re-fetch live ORM objects inside this session
                chunk_ids = [c.id for c in batch]
                stmt = select(RawMessageChunk).where(RawMessageChunk.id.in_(chunk_ids))
                res = await session.execute(stmt)
                live_batch = list(res.scalars().all())

                succeeded = await _process_batch(
                    live_batch,
                    llm_structured,
                    embeddings_model,
                    qdrant_client,
                    session,
                )
                total_processed += succeeded
                total_failed += len(batch) - succeeded
        except Exception as exc:
            log.error(
                "extract_embed_batch_error",
                rawfile_id=rawfile_id,
                batch=batch_idx + 1,
                error=str(exc),
            )
            total_failed += len(batch)

    await qdrant_client.close()

    log.info(
        "extract_embed_done",
        rawfile_id=rawfile_id,
        processed=total_processed,
        failed=total_failed,
    )
    return {
        "status": "COMPLETED",
        "rawfile_id": rawfile_id,
        "processed": total_processed,
        "failed": total_failed,
    }