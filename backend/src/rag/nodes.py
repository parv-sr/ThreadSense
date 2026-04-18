from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from backend.src.core.config import get_settings
from backend.src.rag.tools import hybrid_retrieve
from backend.src.schemas.rag import AnswerWithSources, GradedListing, ParsedQuery

logger = structlog.get_logger(__name__)
settings = get_settings()

# Deterministic graph nodes reuse singleton model clients to avoid per-request construction overhead.
_parser_llm: ChatOpenAI = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)
_grader_llm: ChatOpenAI = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)
_final_llm: ChatOpenAI = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)


async def query_parser_node(state: dict[str, Any]) -> dict[str, Any]:
    """Parse the user query into explicit hard constraints plus soft preferences."""

    query_text: str = str(state.get("query") or "")
    parser: Any = _parser_llm.with_structured_output(ParsedQuery)
    parsed_query: ParsedQuery = await parser.ainvoke(
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
    logger.info("rag_query_parsed", parsed_query=parsed_query.model_dump())
    return {"parsed_query": parsed_query}


async def build_hard_filter_node(state: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic Qdrant hard filters before any vector retrieval for max precision/recall."""

    parsed_query: ParsedQuery | None = state.get("parsed_query")
    must_conditions: list[FieldCondition] = []

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
        must_conditions.append(FieldCondition(key="location", match=MatchValue(value=parsed_query.location)))
    if parsed_query.parkings_required is not None:
        must_conditions.append(
            FieldCondition(
                key="parking",
                range=Range(gte=parsed_query.parkings_required),
            )
        )

    qdrant_filter: Filter | None = Filter(must=must_conditions) if must_conditions else None

    hard_filters: dict[str, Any] = {
        "price_min": parsed_query.price_min,
        "price_max": parsed_query.price_max,
        "bhk_min": parsed_query.bhk_min,
        "bhk_max": parsed_query.bhk_max,
        "area_min": parsed_query.area_min,
        "area_max": parsed_query.area_max,
        "location": parsed_query.location,
        "parkings_required": parsed_query.parkings_required,
    }
    parsed_query.hard_filters = {k: v for k, v in hard_filters.items() if v is not None}
    logger.info("rag_hard_filter_built", hard_filters=parsed_query.hard_filters)
    return {"qdrant_filter": qdrant_filter, "parsed_query": parsed_query}


async def hybrid_retrieval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute hybrid dense+sparse retrieval on the already hard-filtered candidate set."""

    query_text: str = str(state.get("query") or "")
    qdrant_filter: Filter | None = state.get("qdrant_filter")
    docs: list[Document] = await hybrid_retrieve.ainvoke(
        {"query": query_text, "filters": None, "qdrant_filter": qdrant_filter}
    )
    return {"retrieved_listings": docs}


async def rerank_grader_node(state: dict[str, Any]) -> dict[str, Any]:
    """Grade retrieved listings with a fast LLM; keep deterministic IDs and explain validity."""

    docs: list[Document] = list(state.get("retrieved_listings") or [])
    parsed_query: ParsedQuery | None = state.get("parsed_query")
    soft_preferences: str = parsed_query.soft_preferences if parsed_query is not None else ""

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

    grader: Any = _grader_llm.with_structured_output(list[GradedListing])
    graded_listings: list[GradedListing] = await grader.ainvoke(
        [
            SystemMessage(
                content=(
                    "You grade real estate results. "
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
    logger.info("rag_listings_graded", graded_count=len(graded_listings))
    return {"graded_listings": graded_listings}


async def final_answer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate strictly structured answer with citations + confidence for API response."""

    docs: list[Document] = list(state.get("retrieved_listings") or [])
    graded_listings: list[GradedListing] = list(state.get("graded_listings") or [])
    query_text: str = str(state.get("query") or "")

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
                "relevance_score": grade.relevance_score,
                "reason": grade.reason,
                "price": metadata.get("price"),
                "bhk": metadata.get("bhk"),
                "area_sqft": metadata.get("area_sqft"),
                "location": metadata.get("location"),
                "parking": metadata.get("parking"),
                "chunk_id": metadata.get("chunk_id"),
            }
        )

    answer_builder: Any = _final_llm.with_structured_output(AnswerWithSources)
    final_answer: AnswerWithSources = await answer_builder.ainvoke(
        [
            SystemMessage(
                content=(
                    "Produce AnswerWithSources. "
                    "answer must clearly explain how results match constraints. "
                    "table_html must be valid HTML table rows with listing_id and source citation. "
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
    return {"final_answer": final_answer}
