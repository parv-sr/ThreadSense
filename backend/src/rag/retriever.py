from __future__ import annotations

import re
from typing import Any

import structlog
from langchain_core.documents import Document
from sqlalchemy import select

from backend.src.db.session import AsyncSessionLocal
from backend.src.embeddings.service import EmbeddingService
from backend.src.models.preprocessing import ListingChunk, PropertyListing
from backend.src.rag.query_parser import parse_query_constraints

logger = structlog.get_logger(__name__)


def normalize_location(text: str | None) -> str | None:
    if not text:
        return None
    normalized = str(text).lower()
    normalized = normalized.replace(" west", " w").replace(" east", " e")
    normalized = normalized.replace("w.", "w").replace("e.", "e")
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    normalized = " ".join(normalized.split())
    aliases = {
        "bandra w": "bandra west",
        "bandra west": "bandra west",
        "bandra e": "bandra east",
        "khar w": "khar west",
        "khar west": "khar west",
        "khar e": "khar east",
        "bkc": "bkc",
    }
    return aliases.get(normalized, normalized) or None


class PgvectorListingRetriever:
    """PostgreSQL/pgvector retriever with SQL filters applied before vector ordering."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()

    @staticmethod
    def _apply_filters(stmt, filters: dict[str, Any] | None):
        if not filters:
            return stmt

        if bhk := filters.get("bhk"):
            stmt = stmt.where(PropertyListing.bhk == float(bhk))
        if filters.get("bhk_min") is not None:
            stmt = stmt.where(PropertyListing.bhk >= float(filters["bhk_min"]))
        if filters.get("bhk_max") is not None:
            stmt = stmt.where(PropertyListing.bhk <= float(filters["bhk_max"]))

        location = normalize_location(filters.get("location"))
        if location:
            stmt = stmt.where(PropertyListing.canonical_location == location)

        if sender := filters.get("sender"):
            stmt = stmt.where(PropertyListing.sender.ilike(f"%{sender}%"))
        if listing_id := filters.get("listing_id"):
            stmt = stmt.where(PropertyListing.id == listing_id)
        if transaction_type := filters.get("transaction_type"):
            stmt = stmt.where(PropertyListing.transaction_type == str(transaction_type).upper())
        if property_type := filters.get("property_type"):
            stmt = stmt.where(PropertyListing.property_type == str(property_type).upper())
        if listing_intent := filters.get("listing_intent"):
            stmt = stmt.where(PropertyListing.listing_intent == str(listing_intent).upper())

        min_price = filters.get("min_price") if filters.get("min_price") is not None else filters.get("price_min")
        max_price = filters.get("max_price") if filters.get("max_price") is not None else filters.get("price_max")
        if min_price is not None:
            stmt = stmt.where(PropertyListing.price_min >= int(min_price))
        if max_price is not None:
            stmt = stmt.where(PropertyListing.price_max <= int(max_price))

        area_min = filters.get("area_min") if filters.get("area_min") is not None else filters.get("min_sqft")
        area_max = filters.get("area_max") if filters.get("area_max") is not None else filters.get("max_sqft")
        if area_min is not None:
            stmt = stmt.where(PropertyListing.sqft >= int(area_min))
        if area_max is not None:
            stmt = stmt.where(PropertyListing.sqft <= int(area_max))

        if furnishing := filters.get("furnishing"):
            stmt = stmt.where(PropertyListing.furnishing == str(furnishing).upper().replace("_", "-"))

        return stmt

    @staticmethod
    def _to_document(listing: PropertyListing, chunk: ListingChunk, distance: float | None = None) -> Document:
        metadata = {
            "listing_id": str(listing.id),
            "chunk_id": str(listing.raw_chunk_id),
            "listing_chunk_id": str(chunk.id),
            "transaction_type": getattr(listing.transaction_type, "value", str(listing.transaction_type)),
            "property_type": getattr(listing.property_type, "value", str(listing.property_type)),
            "listing_intent": getattr(listing.listing_intent, "value", str(listing.listing_intent)),
            "price": listing.price,
            "price_min": listing.price_min,
            "price_max": listing.price_max,
            "price_status": getattr(listing.price_status, "value", str(listing.price_status)),
            "bhk": listing.bhk,
            "sqft": listing.sqft,
            "location": listing.location,
            "canonical_location": listing.canonical_location,
            "furnishing": getattr(listing.furnishing, "value", str(listing.furnishing))
            if listing.furnishing is not None
            else None,
            "pets_allowed": listing.pets_allowed,
            "sender": listing.sender,
            "timestamp": listing.timestamp.isoformat() if listing.timestamp else None,
            "contact_number": listing.contact_number,
            "landmark": listing.landmark,
            "floor_number": listing.floor_number,
            "total_floors": listing.total_floors,
            "is_verified": listing.is_verified,
            "confidence_score": listing.confidence_score,
            "semantic_distance": distance,
        }
        return Document(page_content=chunk.content, metadata=metadata)

    @staticmethod
    def _lexical_rerank(
        *,
        docs: list[Document],
        query: str,
        parsed_filters: dict[str, Any],
        top_k: int,
    ) -> list[Document]:
        tokens: list[str] = [token for token in re.split(r"\W+", query.lower()) if len(token) > 2]
        weighted: list[tuple[float, Document]] = []
        for rank_index, doc in enumerate(docs):
            metadata: dict[str, Any] = doc.metadata or {}
            haystack = " ".join(
                [
                    str(doc.page_content or ""),
                    str(metadata.get("location") or ""),
                    str(metadata.get("property_type") or ""),
                    str(metadata.get("transaction_type") or ""),
                ]
            ).lower()
            lexical_score = sum(1 for token in tokens if token in haystack) / max(1, len(tokens))
            vector_prior = 1.0 / (1.0 + rank_index)
            filter_bonus = 0.0
            if parsed_filters.get("location") is not None:
                location_value = normalize_location(str(metadata.get("location") or ""))
                expected = normalize_location(str(parsed_filters["location"]))
                if expected and location_value and expected in location_value:
                    filter_bonus += 0.20
            if parsed_filters.get("bhk") is not None:
                try:
                    if abs(float(metadata.get("bhk")) - float(parsed_filters["bhk"])) <= 0.51:
                        filter_bonus += 0.20
                except (TypeError, ValueError):
                    pass
            weighted.append(((vector_prior * 0.35) + (lexical_score * 0.45) + filter_bonus, doc))
        weighted.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in weighted[:top_k]]

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        parsed_filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[Document]:
        constraints = parse_query_constraints(query) if parsed_filters is None else None
        merged_filters: dict[str, Any] = (
            dict(parsed_filters)
            if parsed_filters is not None
            else {**(constraints.filters if constraints is not None else {}), **(filters or {})}
        )
        normalized_query = constraints.normalized_query if constraints is not None else query

        query_embedding = await self.embedding_service.embed_text(normalized_query or query)
        distance = ListingChunk.embedding.cosine_distance(query_embedding).label("semantic_distance")
        stmt = (
            select(PropertyListing, ListingChunk, distance)
            .join(ListingChunk, ListingChunk.property_listing_id == PropertyListing.id)
            .where(ListingChunk.embedding.is_not(None))
        )
        stmt = self._apply_filters(stmt, merged_filters)
        stmt = stmt.order_by(distance).limit(max(1, limit))

        async with AsyncSessionLocal() as session:
            rows = (await session.execute(stmt)).all()

        docs = [self._to_document(listing, chunk, float(dist)) for listing, chunk, dist in rows]
        logger.info(
            "pgvector_retrieval_done",
            count=len(docs),
            filters=merged_filters or None,
            limit=limit,
        )
        return docs
