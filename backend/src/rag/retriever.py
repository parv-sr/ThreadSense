from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document
from qdrant_client.http import models as qmodels

logger = structlog.get_logger(__name__)


class HybridQdrantRetriever:
    """Hybrid (dense + sparse/BM25) retriever over QdrantVectorStore."""

    def __init__(self, vector_store: Any) -> None:
        self.vector_store = vector_store

    @staticmethod
    def _to_qdrant_filter(filters: dict[str, Any] | None) -> qmodels.Filter | None:
        """Convert API filters to a Qdrant filter expression."""

        if not filters:
            return None

        must: list[qmodels.FieldCondition] = []
        if location := filters.get("location"):
            must.append(qmodels.FieldCondition(key="location", match=qmodels.MatchText(text=str(location))))
        if sender := filters.get("sender"):
            must.append(qmodels.FieldCondition(key="sender", match=qmodels.MatchText(text=str(sender))))
        if bhk := filters.get("bhk"):
            must.append(qmodels.FieldCondition(key="bhk", match=qmodels.MatchValue(value=str(bhk))))
        if listing_id := filters.get("listing_id"):
            must.append(qmodels.FieldCondition(key="listing_id", match=qmodels.MatchValue(value=str(listing_id))))

        min_price = filters.get("min_price")
        max_price = filters.get("max_price")
        if min_price is not None or max_price is not None:
            must.append(
                qmodels.FieldCondition(
                    key="price_numeric",
                    range=qmodels.Range(gte=float(min_price) if min_price is not None else None, lte=float(max_price) if max_price is not None else None),
                )
            )

        return qmodels.Filter(must=must) if must else None

    async def retrieve(self, query: str, *, filters: dict[str, Any] | None = None, limit: int = 20) -> list[Document]:
        """Run hybrid retrieval with metadata filters against Qdrant."""

        q_filter = self._to_qdrant_filter(filters)
        logger.info("hybrid_retrieve_started", query=query, filters=filters, limit=limit)

        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": limit, "filter": q_filter},
        )
        docs = await retriever.ainvoke(query)

        logger.info("hybrid_retrieve_finished", count=len(docs))
        return list(docs)
