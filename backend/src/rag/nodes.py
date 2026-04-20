from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue, Range

from backend.src.core.config import get_settings
from backend.src.rag.tools import hybrid_retrieve
from backend.src.rag.utils import render_table_html
from backend.src.schemas.rag import (
    AnswerWithSources,
    FinalAnswerLLMOutput,
    GradedListing,
    GradingResponse,
    ParsedQuery,
    ParsedQueryLLMOutput,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Deterministic graph nodes reuse singleton model clients to avoid per-request construction overhead.
_parser_llm: ChatOpenAI = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)
_grader_llm: ChatOpenAI = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)
_final_llm: ChatOpenAI = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)


async def query_parser_node(state: dict[str, Any]) -> dict[str, Any]:
    """Parse the user query into explicit hard constraints plus soft preferences."""

    query_text: str = str(state.get("query") or "")
    logger.info("rag_query_parser_start", query_length=len(query_text))
    parser: Any = _parser_llm.with_structured_output(ParsedQueryLLMOutput)
    llm_output: ParsedQuery = await parser.ainvoke(
        [
            SystemMessage(
                content=(
                    "You convert a property search query into strict fields. "
                    "Return numeric ranges for price/bhk/area when present, exact location when present, "
                    "and parkings_required when specified. Use null for missing values. "
                    "Hard filters are strict constraints; soft_preferences are non-blocking preferences."
                )
            ),
            HumanMessage(content=query_text),
        ]
    )
    parsed_query = ParsedQuery(**llm_output.model_dump())


    logger.info("rag_query_parsed", parsed_query=parsed_query.model_dump())
    return {"parsed_query": parsed_query}


async def build_hard_filter_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic Qdrant hard filters before any vector retrieval for max precision/recall."""

    parsed_query: ParsedQuery | None = state.get("parsed_query")
    must_conditions: list[FieldCondition] = []
    logger.info("rag_hard_filter_start", has_parsed_query=parsed_query is not None)

    if parsed_query is None:
        return {"qdrant_filter": None}

    if parsed_query.price_min is not None or parsed_query.price_max is not None:
        must_conditions.append(
            FieldCondition(
                key="price",
                range=Range(gte=parsed_query.price_min, lte=parsed_query.price_max),
            )
        )
    if parsed_query.bhk_min is not None or parsed_query.bhk_max is not None:
        must_conditions.append(
            FieldCondition(
                key="bhk",
                range=Range(gte=parsed_query.bhk_min, lte=parsed_query.bhk_max),
            )
        )
    if parsed_query.area_min is not None or parsed_query.area_max is not None:
        must_conditions.append(
            FieldCondition(
                key="area_sqft",
                range=Range(gte=parsed_query.area_min, lte=parsed_query.area_max),
            )
        )
    if parsed_query.location:
        must_conditions.append(FieldCondition(key="location", match=MatchText(text=parsed_query.location)))
    if parsed_query.transaction_type:
        must_conditions.append(
            FieldCondition(
                key="transaction_type",
                match=MatchValue(value=parsed_query.transaction_type.upper()),
            )
        )
    if parsed_query.property_type:
        must_conditions.append(
            FieldCondition(
                key="property_type",
                match=MatchValue(value=parsed_query.property_type.upper()),
            )
        )
    if parsed_query.parkings_required is not None:
        must_conditions.append(
            FieldCondition(
                key="parking",
                range=Range(gte=parsed_query.parkings_required),
            )
        )

    qdrant_filter: Filter | None = Filter(must=must_conditions) if must_conditions else None
    serialized_qdrant_filter: dict[str, Any] | None = (
        qdrant_filter.model_dump(mode="json", exclude_none=True) if qdrant_filter is not None else None
    )

    hard_filters: dict[str, Any] = {
        "price_min": parsed_query.price_min,
        "price_max": parsed_query.price_max,
        "bhk_min": parsed_query.bhk_min,
        "bhk_max": parsed_query.bhk_max,
        "area_min": parsed_query.area_min,
        "area_max": parsed_query.area_max,
        "location": parsed_query.location,
        "transaction_type": parsed_query.transaction_type,
        "property_type": parsed_query.property_type,
        "listing_intent": parsed_query.listing_intent,
        "parkings_required": parsed_query.parkings_required,
    }
    resolved_hard_filters: dict[str, Any] = {k: v for k, v in hard_filters.items() if v is not None}
    updated_query: ParsedQuery = parsed_query.model_copy(update={"hard_filters": resolved_hard_filters})
    logger.info("rag_hard_filter_built", hard_filters=resolved_hard_filters)
    logger.info("rag_qdrant_filter_serialized", qdrant_filter=serialized_qdrant_filter)
    return {"qdrant_filter": qdrant_filter, "parsed_query": updated_query}


async def hybrid_retrieval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute hybrid dense+sparse retrieval on the already hard-filtered candidate set."""

    query_text: str = str(state.get("query") or "")
    qdrant_filter: Filter | None = state.get("qdrant_filter")
    parsed_query: ParsedQuery | None = state.get("parsed_query")
    logger.info(
        "rag_hybrid_retrieval_start",
        query_length=len(query_text),
        has_qdrant_filter=qdrant_filter is not None,
        has_parsed_query=parsed_query is not None,
    )
    explicit_filters: dict[str, Any] = (
        {
            k: v
            for k, v in {
                "bhk": parsed_query.bhk_min if parsed_query else None,
                "min_price": parsed_query.price_min if parsed_query else None,
                "max_price": parsed_query.price_max if parsed_query else None,
                "location": parsed_query.location if parsed_query else None,
                "transaction_type": parsed_query.transaction_type if parsed_query else None,
                "property_type": parsed_query.property_type if parsed_query else None,
                "listing_intent": parsed_query.listing_intent if parsed_query else None,
            }.items()
            if v is not None
        }
        if parsed_query
        else {}
    )
    docs: list[Document] = await hybrid_retrieve.ainvoke(
        {
            "query": query_text,
            "filters": explicit_filters,
            "parsed_filters": explicit_filters,
            "qdrant_filter": qdrant_filter,
        }
    )
    logger.info("rag_retrieval_complete", retrieved_count=len(docs))
    if docs:
        first_doc_metadata: dict[str, Any] = dict(docs[0].metadata or {})
        logger.info("rag_retrieval_first_doc_metadata", metadata=first_doc_metadata)
    return {"retrieved_listings": docs}


async def rerank_grader_node(state: dict[str, Any]) -> dict[str, Any]:
    """Grade retrieved listings with a fast LLM; keep deterministic IDs and explain validity."""

    docs: list[Document] = list(state.get("retrieved_listings") or [])
    parsed_query: ParsedQuery | None = state.get("parsed_query")
    soft_preferences: str = parsed_query.soft_preferences if parsed_query is not None else ""
    logger.info(
        "rag_grader_start",
        retrieved_count=len(docs),
        soft_preferences_present=bool(soft_preferences),
    )

    evidence: list[dict[str, Any]] = []
    for doc in docs:
        metadata: dict[str, Any] = dict(doc.metadata or {})
        listing_id: str = str(metadata.get("listing_id") or metadata.get("chunk_id") or "")
        evidence.append(
            {
                "listing_id": listing_id,
                "metadata": metadata,
                "preview": str(doc.page_content)[:500],
            }
        )

    grader: Any = _grader_llm.with_structured_output(GradingResponse)
    response: GradingResponse = await grader.ainvoke(
        [
            SystemMessage(
                content=(
                    "You grade real estate results. "
                    "Return a JSON object with a `results` array. Each element is one GradedListing. "
                    "Return one GradedListing per input listing_id. relevance_score must be 0..1. "
                    "is_valid=true only if listing satisfies hard constraints and matches query intent."
                )
            ),
            HumanMessage(
                content=(
                    f"Soft preferences: {soft_preferences}\n"
                    f"Parsed hard filters: {json.dumps((parsed_query.hard_filters if parsed_query else {}), default=str)}\n"
                    f"Listings JSON: {json.dumps(evidence, default=str)}"
                )
            ),
        ]
    )
    graded_listings: list[GradedListing] = response.results
    valid_count: int = sum(1 for listing in graded_listings if listing.is_valid)
    invalid_count: int = sum(1 for listing in graded_listings if not listing.is_valid)
    logger.info("rag_grading_summary", valid_count=valid_count, invalid_count=invalid_count)
    invalid_listings: list[GradedListing] = [listing for listing in graded_listings if not listing.is_valid]
    for invalid_listing in invalid_listings[:2]:
        logger.info(
            "rag_rejection_reason",
            listing_id=invalid_listing.listing_id,
            reason=invalid_listing.reason,
        )
    logger.info("rag_listings_graded", graded_count=len(graded_listings))
    return {"graded_listings": graded_listings}


async def final_answer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate strictly structured answer with citations + confidence for API response."""

    docs: list[Document] = list(state.get("retrieved_listings") or [])
    graded_listings: list[GradedListing] = list(state.get("graded_listings") or [])
    query_text: str = str(state.get("query") or "")
    logger.info(
        "rag_final_answer_start",
        retrieved_count=len(docs),
        graded_count=len(graded_listings),
        query_length=len(query_text),
    )

    doc_map: dict[str, Document] = {}
    for doc in docs:
        metadata: dict[str, Any] = dict(doc.metadata or {})
        listing_id: str = str(metadata.get("listing_id") or metadata.get("chunk_id") or "")
        if listing_id:
            doc_map[listing_id] = doc

    ranked_valid: list[GradedListing] = sorted(
        [grade for grade in graded_listings if grade.is_valid],
        key=lambda item: item.relevance_score,
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    for grade in ranked_valid[:12]:
        selected_doc: Document | None = doc_map.get(grade.listing_id)
        metadata = dict((selected_doc.metadata if selected_doc else {}) or {})
        selected.append(
            {
                "listing_id": grade.listing_id,
                "chunk_id": metadata.get("chunk_id"),
                "relevance_score": grade.relevance_score,
                "reason": grade.reason,
                "price": metadata.get("price"),
                "bhk": metadata.get("bhk"),
                "area_sqft": metadata.get("area_sqft"),
                "location": metadata.get("location"),
                "landmark": metadata.get("landmark"),
                "furnished": metadata.get("furnished"),
                "floor_number": metadata.get("floor_number"),
                "total_floors": metadata.get("total_floors"),
                "parking": metadata.get("parking"),
                "contact_number": metadata.get("contact_number"),
                "sender": metadata.get("sender"),
                "timestamp": metadata.get("timestamp"),
                "transaction_type": metadata.get("transaction_type"),
                "property_type": metadata.get("property_type"),
                "is_verified": metadata.get("is_verified"),
                "confidence_score": metadata.get("confidence_score"),
            }
        )

    logger.info("rag_final_selection_count", selected_count=len(selected))
    answer_builder: Any = _final_llm.with_structured_output(FinalAnswerLLMOutput)
    llm_answer: FinalAnswerLLMOutput = await answer_builder.ainvoke(
        [
            SystemMessage(
                content=(
                    "Produce AnswerWithSources. "
                    "answer must clearly explain how results match constraints. "
                    "Do not generate HTML. "
                    "Return only answer, sources, and confidence. "
                    "sources must contain source IDs only. confidence must be 0..1."
                )
            ),
            HumanMessage(
                content=(
                    f"User query: {query_text}\n"
                    f"Ranked listings JSON: {json.dumps(selected, default=str)}"
                )
            ),
        ]
    )
    table_rows: list[dict[str, Any]] = []
    for item in selected:
        table_rows.append(
            {
                "bhk": item.get("bhk", "N/A"),
                "price": item.get("price", "N/A"),
                "location": item.get("location", "N/A"),
                "contact_number": item.get("contact_number", "N/A"),
                "timestamp": item.get("timestamp", "N/A"),
                "sender": item.get("sender", "N/A"),
                "listing_id": item.get("listing_id", ""),
                "chunk_id": item.get("chunk_id", ""),
            }
        )

    table_html: str = render_table_html(table_rows)
    logger.info(
        "rag_final_answer_complete",
        selected_count=len(selected),
        source_count=len(llm_answer.sources),
        confidence=llm_answer.confidence,
    )
    return {
        "final_answer": AnswerWithSources(
            answer=llm_answer.answer,
            table_html=table_html,
            sources=llm_answer.sources,
            confidence=llm_answer.confidence,
        )
    }
