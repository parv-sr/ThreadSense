from __future__ import annotations

import re
from typing import Any

import structlog
from langchain_core.documents import Document
from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue, Range

from backend.src.rag.query_parser import parse_query_constraints

logger = structlog.get_logger(__name__)


class HybridQdrantRetriever:
    """ThreadSense hybrid retriever for dense+sparse Qdrant queries with metadata filters."""

    def __init__(self, vector_store: Any) -> None:
        self.vector_store = vector_store

    @staticmethod
    def _build_filter(filters: dict[str, Any] | None) -> Filter | None:
        """Translate API filters into Qdrant filter syntax."""

        if not filters:
            return None

        must: list[FieldCondition] = []

        if bhk := filters.get("bhk"):
            must.append(FieldCondition(key="bhk", range=Range(gte=float(bhk), lte=float(bhk))))
        if location := filters.get("location"):
            must.append(FieldCondition(key="location", match=MatchText(text=str(location))))
        if sender := filters.get("sender"):
            must.append(FieldCondition(key="sender", match=MatchText(text=str(sender))))
        if listing_id := filters.get("listing_id"):
            must.append(FieldCondition(key="listing_id", match=MatchValue(value=str(listing_id))))
        if transaction_type := filters.get("transaction_type"):
            must.append(
                FieldCondition(
                    key="transaction_type",
                    match=MatchValue(value=str(transaction_type).upper()),
                )
            )
        if property_type := filters.get("property_type"):
            must.append(
                FieldCondition(
                    key="property_type",
                    match=MatchValue(value=str(property_type).upper()),
                )
            )
        if listing_intent := filters.get("listing_intent"):
            must.append(
                FieldCondition(
                    key="listing_intent",
                    match=MatchValue(value=str(listing_intent).upper()),
                )
            )

        min_price = filters.get("min_price")
        max_price = filters.get("max_price")
        if min_price is not None or max_price is not None:
            must.append(
                FieldCondition(
                    key="price",
                    range=Range(
                        gte=float(min_price) if min_price is not None else None,
                        lte=float(max_price) if max_price is not None else None,
                    ),
                )
            )

        return Filter(must=must) if must else None

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        parsed_filters: dict[str, Any] | None = None,
        qdrant_filter: Filter | None = None,
        limit: int = 20,
    ) -> list[Document]:
        """Perform dense retrieval + lexical reranking with optional parsed query filters."""

        constraints = parse_query_constraints(query) if parsed_filters is None else None
        merged_filters: dict[str, Any] = (
            dict(parsed_filters)
            if parsed_filters is not None
            else {**(constraints.filters if constraints is not None else {}), **(filters or {})}
        )
        parsed_filter: Filter | None = self._build_filter(merged_filters or None)
        q_filter: Filter | None = self._merge_filters(parsed_filter, qdrant_filter)
        normalized_query: str = constraints.normalized_query if constraints is not None else query
        parsed_constraints: dict[str, Any] | None = constraints.filters if constraints is not None else None
        logger.info(
            "hybrid_retrieval_start",
            query=query,
            normalized_query=normalized_query,
            parsed_filters=parsed_constraints,
            filters=merged_filters or None,
            limit=limit,
        )

        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": max(limit * 3, 40), "filter": q_filter},
        )
        docs = await retriever.ainvoke(normalized_query or query)
        reranked_docs = self._lexical_rerank(
            docs=list(docs),
            query=normalized_query or query,
            parsed_filters=merged_filters,
            top_k=limit,
        )

        logger.info("hybrid_retrieval_done", count=len(reranked_docs), candidate_count=len(docs))
        return reranked_docs


    @staticmethod
    def _merge_filters(parsed_filter: Filter | None, external_filter: Filter | None) -> Filter | None:
        """Combine parsed query filters with deterministic graph-provided hard filters."""

        if parsed_filter is None:
            return external_filter
        if external_filter is None:
            return parsed_filter

        must: list[Any] = []
        if parsed_filter.must:
            must.extend(parsed_filter.must)
        if external_filter.must:
            must.extend(external_filter.must)
        return Filter(must=must) if must else None

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
            haystack: str = " ".join(
                [
                    str(doc.page_content or ""),
                    str(metadata.get("location") or ""),
                    str(metadata.get("property_type") or ""),
                    str(metadata.get("transaction_type") or ""),
                    str(metadata.get("content") or ""),
                ]
            ).lower()

            lexical_hits: int = sum(1 for token in tokens if token in haystack)
            lexical_score: float = lexical_hits / max(1, len(tokens))
            dense_prior: float = 1.0 / (1.0 + rank_index)
            filter_bonus: float = 0.0

            if parsed_filters.get("location") is not None:
                location_value: str = str(metadata.get("location") or "").lower()
                if str(parsed_filters["location"]).lower() in location_value:
                    filter_bonus += 0.20
            if parsed_filters.get("bhk") is not None:
                try:
                    if abs(float(metadata.get("bhk")) - float(parsed_filters["bhk"])) <= 0.51:
                        filter_bonus += 0.20
                except (TypeError, ValueError):
                    pass
            if parsed_filters.get("transaction_type") is not None:
                if str(metadata.get("transaction_type") or "").upper() == str(parsed_filters["transaction_type"]).upper():
                    filter_bonus += 0.15
            if parsed_filters.get("property_type") is not None:
                if str(metadata.get("property_type") or "").upper() == str(parsed_filters["property_type"]).upper():
                    filter_bonus += 0.10

            final_score: float = (dense_prior * 0.45) + (lexical_score * 0.45) + filter_bonus
            weighted.append((final_score, doc))

        weighted.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in weighted[:top_k]]
