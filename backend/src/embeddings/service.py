from __future__ import annotations

from typing import Any

import structlog
from langchain_openai import OpenAIEmbeddings
from qdrant_client import AsyncQdrantClient, models as qmodels

from backend.src.core.config import get_settings
from backend.src.models.preprocessing import PropertyListing

log = structlog.get_logger(__name__)
settings = get_settings()

QDRANT_COLLECTION = "threadsense_listings"


class EmbeddingService:
    def __init__(self) -> None:
        self.embedding_model_name = settings.openai_embedding_model
        self.qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self.embeddings = OpenAIEmbeddings(model=self.embedding_model_name, api_key=settings.openai_api_key)

    async def _vector_size(self) -> int:
        sample = await self.embeddings.aembed_query("threadsense-vector-size-probe")
        return len(sample)

    async def ensure_collection(self) -> None:
        collections = await self.qdrant.get_collections()
        existing = {c.name for c in collections.collections}
        if QDRANT_COLLECTION in existing:
            return
        await self.qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=await self._vector_size(), distance=qmodels.Distance.COSINE),
        )
        log.info("qdrant_collection_created", collection=QDRANT_COLLECTION)

    async def embed_text(self, text: str) -> list[float]:
        return await self.embeddings.aembed_query(text)

    async def upsert_listing_vector(
        self,
        *,
        point_id: str,
        vector: list[float],
        listing: PropertyListing,
        chunk_content: str,
    ) -> None:
        payload: dict[str, Any] = {
            "listing_id": str(listing.id),
            "raw_chunk_id": str(listing.raw_chunk_id),
            "property_type": listing.property_type.value,
            "bhk": listing.bhk,
            "price": listing.price,
            "location": listing.location,
            "contact_number": listing.contact_number,
            "sender": listing.sender,
            "timestamp": listing.timestamp.isoformat() if listing.timestamp else None,
            "furnished": listing.furnished.value if listing.furnished else None,
            "floor_number": listing.floor_number,
            "total_floors": listing.total_floors,
            "area_sqft": listing.area_sqft,
            "landmark": listing.landmark,
            "is_verified": listing.is_verified,
            "confidence_score": listing.confidence_score,
            "status": listing.status.value,
            "raw_llm_output": listing.raw_llm_output,
            "content": chunk_content,
        }
        await self.qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
        )

    async def close(self) -> None:
        await self.qdrant.close()
