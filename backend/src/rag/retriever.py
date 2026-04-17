from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document
from qdrant_client.http import models as qmodels

logger = structlog.get_logger(__name__)


class HybridQdrantRetriever:
    """ThreadSense hybrid retriever for dense+sparse Qdrant queries with metadata filters."""

    def __init__(self, vector_store: Any) -> None:
        self.vector_store = vector_store

    @staticmethod
    def _build_filter(filters: dict[str, Any] | None) -> qmodels.Filter | None:
        """Translate API filters into Qdrant filter syntax."""

        if not filters:
            return None

        must: list[qmodels.Condition] = []

        if bhk := filters.get("bhk"):
            try:
                bhk_value: float = float(bhk)
                must.append(
                    qmodels.FieldCondition(
                        key="bhk",
                        range=qmodels.Range(gte=bhk_value - 0.01, lte=bhk_value + 0.01),
                    )
                )
            except (TypeError, ValueError):
                must.append(qmodels.FieldCondition(key="bhk", match=qmodels.MatchValue(value=bhk)))
        if location := filters.get("location"):
            must.append(qmodels.FieldCondition(key="location", match=qmodels.MatchText(text=str(location))))
        if sender := filters.get("sender"):
            must.append(qmodels.FieldCondition(key="sender", match=qmodels.MatchText(text=str(sender))))
        if listing_id := filters.get("listing_id"):
            must.append(qmodels.FieldCondition(key="listing_id", match=qmodels.MatchValue(value=str(listing_id))))

        min_price = filters.get("min_price")
        max_price = filters.get("max_price")
        if min_price is not None or max_price is not None:
            must.append(
                qmodels.FieldCondition(
                    key="price_numeric",
                    range=qmodels.Range(
                        gte=float(min_price) if min_price is not None else None,
                        lte=float(max_price) if max_price is not None else None,
                    ),
                )
            )

        return qmodels.Filter(must=must) if must else None

    async def retrieve(self, query: str, *, filters: dict[str, Any] | None = None, limit: int = 20) -> list[Document]:
        """Perform async hybrid retrieval through LangChain's QdrantVectorStore retriever."""

        q_filter = self._build_filter(filters)
        logger.info("hybrid_retrieval_start", query=query, filters=filters, limit=limit)

        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": limit, "filter": q_filter},
        )
        docs = await retriever.ainvoke(query)

        logger.info("hybrid_retrieval_done", count=len(docs))
        return list(docs)
