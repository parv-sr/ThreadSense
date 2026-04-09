from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document

log = structlog.get_logger(__name__)

try:
    from langchain_qdrant import QdrantVectorStore
except Exception:  # noqa: BLE001
    QdrantVectorStore = Any  # type: ignore[misc,assignment]


class HybridQdrantRetriever:
    """Hybrid retriever wrapper for vector + keyword + metadata filters."""

    def __init__(self, vector_store: QdrantVectorStore) -> None:
        self.vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[Document]:
        log.info("hybrid_retrieve_start", query=query, filters=filters, limit=limit)
        # Hybrid search mode is selected via `search_type="mmr"` + metadata filters.
        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": limit, "fetch_k": max(limit * 2, 40), "filter": filters or {}},
        )
        docs = await retriever.ainvoke(query)
        log.info("hybrid_retrieve_done", count=len(docs))
        return list(docs)
