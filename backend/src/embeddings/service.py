from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.src.core.config import get_settings
from backend.src.embeddings.constants import QDRANT_COLLECTION, QDRANT_VECTOR_NAME
from backend.src.models.preprocessing import ListingChunk, PropertyListing

log = structlog.get_logger(__name__)
settings = get_settings()


class QdrantListingPayload(BaseModel):
    listing_id: str
    chunk_id: str
    property_type: str
    transaction_type: str
    listing_intent: str
    bhk: float | None = None
    price: int | None = None
    location: str | None = None
    contact_number: str | None = None
    sender: str | None = None
    timestamp: str | None = None
    furnished: str | None = None
    floor_number: int | None = None
    total_floors: int | None = None
    area_sqft: int | None = None
    landmark: str | None = None
    is_verified: bool
    confidence_score: float
    status: str
    raw_llm_output: str | None = None
    content: str


class EmbeddingService:
    def __init__(self) -> None:
        self.embedding_model_name: str = settings.openai_embedding_model
        self.qdrant: AsyncQdrantClient = AsyncQdrantClient(
            url=settings.qdrant_endpoint,
            api_key=settings.qdrant_api_key,
        )
        self.embeddings: OpenAIEmbeddings = OpenAIEmbeddings(
            model=self.embedding_model_name,
            api_key=settings.openai_api_key,
        )
        self._collection_ready: bool = False

    async def _vector_size(self) -> int:
        sample: list[float] = await self.embeddings.aembed_query("threadsense-vector-size-probe")
        return len(sample)

    async def ensure_collection(self) -> None:
        if self._collection_ready:
            log.debug("qdrant_collection_already_ready", collection=QDRANT_COLLECTION)
            return

        collections = await self.qdrant.get_collections()
        existing: set[str] = {c.name for c in collections.collections}
        log.info("qdrant_collection_check", collection=QDRANT_COLLECTION, exists=QDRANT_COLLECTION in existing)
        if QDRANT_COLLECTION in existing:
            info = await self.qdrant.get_collection(QDRANT_COLLECTION)
            vectors_cfg: Any = getattr(info.config.params, "vectors", None)
            vector_names: set[str] = set(vectors_cfg.keys()) if isinstance(vectors_cfg, dict) else {""}
            if QDRANT_VECTOR_NAME not in vector_names:
                raise RuntimeError(
                    "Qdrant collection vector schema mismatch. "
                    f"Expected '{QDRANT_VECTOR_NAME}', found {sorted(vector_names)}."
                )
        else:
            await self.qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config={
                    QDRANT_VECTOR_NAME: qmodels.VectorParams(
                        size=await self._vector_size(),
                        distance=qmodels.Distance.COSINE,
                    )
                },
            )
            log.info("qdrant_collection_created", collection=QDRANT_COLLECTION)

        await self.qdrant.create_payload_index(QDRANT_COLLECTION, "bhk", field_schema=qmodels.PayloadSchemaType.FLOAT)
        await self.qdrant.create_payload_index(QDRANT_COLLECTION, "location", field_schema=qmodels.PayloadSchemaType.TEXT)
        await self.qdrant.create_payload_index(QDRANT_COLLECTION, "sender", field_schema=qmodels.PayloadSchemaType.KEYWORD)
        await self.qdrant.create_payload_index(QDRANT_COLLECTION, "price", field_schema=qmodels.PayloadSchemaType.INTEGER)
        await self.qdrant.create_payload_index(
            QDRANT_COLLECTION, "transaction_type", field_schema=qmodels.PayloadSchemaType.KEYWORD
        )
        await self.qdrant.create_payload_index(
            QDRANT_COLLECTION, "property_type", field_schema=qmodels.PayloadSchemaType.KEYWORD
        )
        await self.qdrant.create_payload_index(
            QDRANT_COLLECTION, "listing_intent", field_schema=qmodels.PayloadSchemaType.KEYWORD
        )
        await self.qdrant.create_payload_index(
            QDRANT_COLLECTION, "chunk_id", field_schema=qmodels.PayloadSchemaType.KEYWORD
        )
        self._collection_ready = True
        log.info("qdrant_collection_ready", collection=QDRANT_COLLECTION)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        return await self.embeddings.aembed_query(text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def upsert_listing_vector(
        self,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any] | None = None,
        listing: PropertyListing | None = None,
        chunk_content: str | None = None,
    ) -> None:
        final_payload: dict[str, Any]
        if payload is not None:
            final_payload = payload
        elif listing is not None and chunk_content is not None:
            fallback_payload: QdrantListingPayload = QdrantListingPayload(
                listing_id=str(listing.id),
                chunk_id=str(listing.raw_chunk_id),
                property_type=listing.property_type.value,
                transaction_type=listing.transaction_type.value,
                listing_intent=listing.listing_intent.value,
                bhk=listing.bhk,
                price=listing.price,
                location=listing.location,
                contact_number=listing.contact_number,
                sender=listing.sender,
                timestamp=listing.timestamp.isoformat() if listing.timestamp else None,
                furnished=listing.furnished.value if listing.furnished else None,
                floor_number=listing.floor_number,
                total_floors=listing.total_floors,
                area_sqft=listing.area_sqft,
                landmark=listing.landmark,
                is_verified=listing.is_verified,
                confidence_score=listing.confidence_score,
                status=listing.status.value,
                raw_llm_output=listing.raw_llm_output,
                content=chunk_content,
            )
            final_payload = fallback_payload.model_dump()
        else:
            raise ValueError("Either payload or (listing and chunk_content) must be provided for upsert.")

        await self.qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector={QDRANT_VECTOR_NAME: vector},
                    payload=final_payload,
                )
            ],
        )

    async def embed_and_upsert_listing(self, *, listing: PropertyListing, session: AsyncSession) -> None:
        log.info("embedding_listing_start", listing_id=str(listing.id), raw_chunk_id=str(listing.raw_chunk_id))
        await self.ensure_collection()

        stmt = select(ListingChunk).where(ListingChunk.listing_id == listing.id).order_by(ListingChunk.chunk_index)
        chunks: list[ListingChunk] = list((await session.execute(stmt)).scalars().all())
        if not chunks:
            raise ValueError(f"No listing chunks to embed for listing_id={listing.id}")
        log.info("embedding_listing_chunks_loaded", listing_id=str(listing.id), chunk_count=len(chunks))

        for chunk in chunks:
            try:
                payload_model: QdrantListingPayload = QdrantListingPayload(
                    listing_id=str(listing.id),
                    chunk_id=str(listing.raw_chunk_id),
                    property_type=listing.property_type.value,
                    transaction_type=listing.transaction_type.value,
                    listing_intent=listing.listing_intent.value,
                    bhk=listing.bhk,
                    price=listing.price,
                    location=listing.location,
                    contact_number=listing.contact_number,
                    sender=listing.sender,
                    timestamp=listing.timestamp.isoformat() if listing.timestamp else None,
                    furnished=listing.furnished.value if listing.furnished else None,
                    floor_number=listing.floor_number,
                    total_floors=listing.total_floors,
                    area_sqft=listing.area_sqft,
                    landmark=listing.landmark,
                    is_verified=listing.is_verified,
                    confidence_score=listing.confidence_score,
                    status=listing.status.value,
                    raw_llm_output=listing.raw_llm_output,
                    content=chunk.content,
                )
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "qdrant_payload_validation_failed",
                    listing_id=str(listing.id),
                    chunk_id=str(chunk.id),
                    field="payload",
                    error=str(exc),
                )
                raise

            vector: list[float] = await self.embed_text(chunk.content)
            point_id: str = chunk.qdrant_point_id or str(uuid4())
            await self.upsert_listing_vector(
                point_id=point_id,
                vector=vector,
                payload=payload_model.model_dump(),
            )
            chunk.qdrant_point_id = point_id
            session.add(chunk)
            log.debug(
                "embedding_chunk_upserted",
                listing_id=str(listing.id),
                chunk_id=str(chunk.id),
                point_id=point_id,
                vector_size=len(vector),
            )
        log.info("embedding_listing_complete", listing_id=str(listing.id), chunk_count=len(chunks))

    async def truncate_all_points(self) -> None:
        log.warning("qdrant_truncate_started", collection=QDRANT_COLLECTION)

        await self.qdrant.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(must=[])
            )
        )

        log.warning("qdrant_truncate_finished", collection=QDRANT_COLLECTION)

    async def close(self) -> None:
        await self.qdrant.close()
