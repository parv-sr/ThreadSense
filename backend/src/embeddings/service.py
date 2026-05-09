from __future__ import annotations

import structlog
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.src.core.config import get_settings
from backend.src.models.preprocessing import ListingChunk, PropertyListing

log = structlog.get_logger(__name__)
settings = get_settings()


class EmbeddingService:
    """OpenRouter-backed embedding writer for PostgreSQL/pgvector."""

    def __init__(self) -> None:
        self.embedding_model_name: str = settings.openrouter_embedding_model
        self.embeddings: OpenAIEmbeddings = OpenAIEmbeddings(
            model=self.embedding_model_name,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

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
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self.embeddings.aembed_documents(texts)

    async def embed_and_upsert_listing(self, *, listing: PropertyListing, session: AsyncSession) -> None:
        log.info("embedding_listing_start", listing_id=str(listing.id), raw_chunk_id=str(listing.raw_chunk_id))
        stmt = (
            select(ListingChunk)
            .where(ListingChunk.property_listing_id == listing.id)
            .order_by(ListingChunk.chunk_index)
        )
        chunks: list[ListingChunk] = list((await session.execute(stmt)).scalars().all())
        if not chunks:
            raise ValueError(f"No listing chunks to embed for listing_id={listing.id}")

        vectors = await self.embed_documents([chunk.content for chunk in chunks])
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
            session.add(chunk)
            log.debug(
                "embedding_chunk_stored",
                listing_id=str(listing.id),
                chunk_id=str(chunk.id),
                vector_size=len(vector),
            )
        log.info("embedding_listing_complete", listing_id=str(listing.id), chunk_count=len(chunks))

    async def truncate_all_points(self, session: AsyncSession) -> None:
        log.warning("embedding_truncate_started")
        await session.execute(update(ListingChunk).values(embedding=None))
        await session.commit()
        log.warning("embedding_truncate_finished")

    async def close(self) -> None:
        return None
