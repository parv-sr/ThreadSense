from __future__ import annotations

from time import perf_counter
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.api.schemas.chat import ChatRequest, ChatResponse, SourceResponse
from backend.src.models.ingestion import RawMessageChunk
from backend.src.models.preprocessing import PropertyListing
from backend.src.rag.graph import rag_app
from backend.src.rag.retriever import PgvectorListingRetriever
from backend.src.rag.tools import clear_retriever_context, set_retriever_context

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Run the LangGraph assistant against PostgreSQL/pgvector inventory."""

    retriever = PgvectorListingRetriever()
    resolved_thread_id: str = payload.thread_id or str(uuid4())
    start_time: float = perf_counter()
    logger.info(
        "chat_pipeline_start",
        thread_id=resolved_thread_id,
        has_existing_thread_id=payload.thread_id is not None,
        query_length=len(payload.message),
    )

    set_retriever_context(retriever)
    try:
        state_input = {"query": payload.message, "thread_id": resolved_thread_id, "hard_filters": {}}
        if payload.use_llm_grading is not None:
            state_input["use_llm_grading"] = payload.use_llm_grading

        result: dict[str, object] = await rag_app.ainvoke(
            state_input,
            config={"configurable": {"thread_id": resolved_thread_id}},
        )
        final_answer: object | None = result.get("final_answer")
        if final_answer is None:
            raise RuntimeError("RAG graph completed without final_answer")

        duration_ms: int = int((perf_counter() - start_time) * 1000)
        sources: list[str] = list(getattr(final_answer, "sources", []))
        logger.info(
            "chat_pipeline_complete",
            thread_id=resolved_thread_id,
            duration_ms=duration_ms,
            sources_count=len(sources),
        )
        return ChatResponse(
            thread_id=resolved_thread_id,
            table_html=str(getattr(final_answer, "table_html", "")),
            reasoning=str(getattr(final_answer, "answer", "")),
            sources=sources,
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms: int = int((perf_counter() - start_time) * 1000)
        logger.exception(
            "chat_graph_failed",
            thread_id=resolved_thread_id,
            duration_ms=duration_ms,
            error=str(exc),
        )
        return ChatResponse(
            thread_id=resolved_thread_id,
            table_html="",
            reasoning="Sorry, I encountered an issue processing your request. Please try again.",
            sources=[],
        )
    finally:
        clear_retriever_context()


@router.get("/source/{listing_id}", response_model=SourceResponse)
async def view_source(listing_id: str, session: AsyncSession = Depends(get_db_session)) -> SourceResponse:
    """Return the exact raw WhatsApp message behind a listing."""

    try:
        parsed_id: UUID = UUID(listing_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="listing_id must be a valid UUID") from exc

    listing: PropertyListing | None = await session.get(PropertyListing, parsed_id)
    if listing is None:
        logger.info("chat_source_listing_not_found", listing_id=listing_id)
        raise HTTPException(status_code=404, detail="Listing not found")

    chunk: RawMessageChunk | None = await session.get(RawMessageChunk, listing.raw_chunk_id)
    if chunk is None:
        logger.info("chat_source_chunk_not_found", listing_id=listing_id, chunk_id=str(listing.raw_chunk_id))
        raise HTTPException(status_code=404, detail="Source chunk not found")

    logger.info("chat_source_resolved", listing_id=listing_id, chunk_id=str(chunk.id), sender=chunk.sender)
    return SourceResponse(
        listing_id=str(listing.id),
        chunk_id=str(chunk.id),
        message_start=chunk.message_start,
        sender=chunk.sender,
        raw_text=chunk.raw_text,
        cleaned_text=chunk.cleaned_text,
        status=chunk.status,
        created_at=chunk.created_at,
    )
