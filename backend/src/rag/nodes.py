from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

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


def _chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openrouter_chat_model,
        temperature=0,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


_parser_llm: ChatOpenAI = _chat_model()
_grader_llm: ChatOpenAI = _chat_model()
_final_llm: ChatOpenAI = _chat_model()


async def query_parser_node(state: dict[str, Any]) -> dict[str, Any]:
    query_text: str = str(state.get("query") or "")
    logger.info("rag_query_parser_start", query_length=len(query_text))
    parser: Any = _parser_llm.with_structured_output(ParsedQueryLLMOutput)
    llm_output: ParsedQuery = await parser.ainvoke(
        [
            SystemMessage(
                content=(
                    "Convert a property search question into strict SQL filter fields. "
                    "Use null for missing values. Put fuzzy wording or comparison goals in soft_preferences."
                )
            ),
            HumanMessage(content=query_text),
        ]
    )
    parsed_query = ParsedQuery(**llm_output.model_dump())
    logger.info("rag_query_parsed", parsed_query=parsed_query.model_dump())
    return {"parsed_query": parsed_query}


async def build_hard_filter_node(state: dict[str, Any]) -> dict[str, Any]:
    parsed_query: ParsedQuery | None = state.get("parsed_query")
    if parsed_query is None:
        return {"hard_filters": {}}

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
    resolved_hard_filters: dict[str, Any] = {key: value for key, value in hard_filters.items() if value is not None}
    updated_query = parsed_query.model_copy(update={"hard_filters": resolved_hard_filters})
    logger.info("rag_hard_filter_built", hard_filters=resolved_hard_filters)
    return {"hard_filters": resolved_hard_filters, "parsed_query": updated_query}


async def hybrid_retrieval_node(state: dict[str, Any]) -> dict[str, Any]:
    query_text: str = str(state.get("query") or "")
    hard_filters: dict[str, Any] = dict(state.get("hard_filters") or {})
    docs: list[Document] = await hybrid_retrieve.ainvoke(
        {
            "query": query_text,
            "filters": hard_filters,
            "parsed_filters": hard_filters,
        }
    )
    logger.info("rag_retrieval_complete", retrieved_count=len(docs), hard_filters=hard_filters)
    return {"retrieved_listings": docs}


async def rerank_grader_node(state: dict[str, Any]) -> dict[str, Any]:
    docs: list[Document] = list(state.get("retrieved_listings") or [])
    parsed_query: ParsedQuery | None = state.get("parsed_query")
    soft_preferences: str = parsed_query.soft_preferences if parsed_query is not None else ""

    evidence: list[dict[str, Any]] = []
    for doc in docs:
        metadata: dict[str, Any] = dict(doc.metadata or {})
        evidence.append(
            {
                "listing_id": str(metadata.get("listing_id") or ""),
                "metadata": metadata,
                "preview": str(doc.page_content)[:500],
            }
        )

    grader: Any = _grader_llm.with_structured_output(GradingResponse)
    response: GradingResponse = await grader.ainvoke(
        [
            SystemMessage(
                content=(
                    "Grade real estate results. Return one GradedListing per listing_id. "
                    "is_valid=true only when the listing satisfies the hard constraints and query intent."
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
    logger.info("rag_listings_graded", graded_count=len(graded_listings))
    return {"graded_listings": graded_listings}


async def final_answer_node(state: dict[str, Any]) -> dict[str, Any]:
    docs: list[Document] = list(state.get("retrieved_listings") or [])
    graded_listings: list[GradedListing] = list(state.get("graded_listings") or [])
    query_text: str = str(state.get("query") or "")

    doc_map: dict[str, Document] = {}
    for doc in docs:
        metadata: dict[str, Any] = dict(doc.metadata or {})
        listing_id: str = str(metadata.get("listing_id") or "")
        if listing_id:
            doc_map[listing_id] = doc

    ranked_valid = sorted(
        [grade for grade in graded_listings if grade.is_valid],
        key=lambda item: item.relevance_score,
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    for grade in ranked_valid[:12]:
        selected_doc = doc_map.get(grade.listing_id)
        metadata = dict((selected_doc.metadata if selected_doc else {}) or {})
        selected.append(
            {
                "listing_id": grade.listing_id,
                "chunk_id": metadata.get("chunk_id"),
                "relevance_score": grade.relevance_score,
                "reason": grade.reason,
                "price": metadata.get("price"),
                "price_min": metadata.get("price_min"),
                "price_max": metadata.get("price_max"),
                "price_status": metadata.get("price_status"),
                "bhk": metadata.get("bhk"),
                "sqft": metadata.get("sqft"),
                "location": metadata.get("location"),
                "furnishing": metadata.get("furnishing"),
                "contact_number": metadata.get("contact_number"),
                "sender": metadata.get("sender"),
                "timestamp": metadata.get("timestamp"),
                "transaction_type": metadata.get("transaction_type"),
                "property_type": metadata.get("property_type"),
                "confidence_score": metadata.get("confidence_score"),
            }
        )

    answer_builder: Any = _final_llm.with_structured_output(FinalAnswerLLMOutput)
    llm_answer: FinalAnswerLLMOutput = await answer_builder.ainvoke(
        [
            SystemMessage(
                content=(
                    "Produce a concise conversational answer. Do not generate HTML. "
                    "Return only answer, sources, and confidence. sources must contain listing IDs."
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
    table_html: str = render_table_html(selected)
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
