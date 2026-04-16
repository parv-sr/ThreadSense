from __future__ import annotations

from typing import Any

import structlog
from langchain_openai import OpenAIEmbeddings
from qdrant_client import AsyncQdrantClient, models as qmodels

from backend.src.core.config import get_settings
from backend.src.embeddings.constants import QDRANT_COLLECTION, QDRANT_VECTOR_NAME
from backend.src.models.preprocessing import PropertyListing

log = structlog.get_logger(__name__)
settings = get_settings()

class EmbeddingService:
    def __init__(self) -> None:
        self.embedding_model_name = settings.openai_embedding_model
        self.qdrant = AsyncQdrantClient(url=settings.qdrant_endpoint, api_key=settings.qdrant_api_key)
        self.embeddings = OpenAIEmbeddings(model=self.embedding_model_name, api_key=settings.openai_api_key)

    async def _vector_size(self) -> int:
        sample = await self.embeddings.aembed_query("threadsense-vector-size-probe")
        return len(sample)

    async def ensure_collection(self) -> None:
        collections = await self.qdrant.get_collections()
        existing = {c.name for c in collections.collections}
        if QDRANT_COLLECTION in existing:
            info = await self.qdrant.get_collection(QDRANT_COLLECTION)
            vectors_cfg = getattr(info.config.params, "vectors", None)
            vector_names: set[str] = set(vectors_cfg.keys()) if isinstance(vectors_cfg, dict) else {""}
            if QDRANT_VECTOR_NAME not in vector_names:
                raise RuntimeError(
                    "Qdrant collection vector schema mismatch. "
                    f"Expected '{QDRANT_VECTOR_NAME}', found {sorted(vector_names)}."
                )
            return
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
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector={QDRANT_VECTOR_NAME: vector},
                    payload=payload,
                )
            ],
        )

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
