from __future__ import annotations

from functools import lru_cache
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.api.schemas.chat import ChatRequest, ChatResponse, SourceResponse
from backend.src.models.ingestion import RawMessageChunk
from backend.src.core.config import get_settings
from backend.src.rag.agent import RAGAgent
from backend.src.rag.retriever import HybridQdrantRetriever

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/chat", tags=["chat"])


def build_rag_agent() -> RAGAgent:
    """Build a production RAG agent using pure dense vectors."""

    collection_name = "threadsense_listings"

    logger.info("rag_agent_build_start", qdrant_url=settings.qdrant_endpoint, collection=collection_name)

    client = QdrantClient(url=settings.qdrant_endpoint, api_key=settings.qdrant_api_key)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=OpenAIEmbeddings(model=settings.openai_embedding_model),
        retrieval_mode=RetrievalMode.DENSE,           # ← Pure dense (simple & stable)
        vector_name="dense",
    )

    retriever = HybridQdrantRetriever(vector_store)
    return RAGAgent(retriever)


@lru_cache(maxsize=1)
def _cached_agent() -> RAGAgent:
    return build_rag_agent()


def get_agent(request: Request) -> RAGAgent:
    """Resolve the initialized app-level agent, falling back to cached singleton."""

    return getattr(request.app.state, "rag_agent", None) or _cached_agent()


@router.post("/", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """Chat with the fully agentic ReAct RAG workflow."""

    agent = get_agent(request)
    try:
        result = await agent.invoke(message=payload.message, thread_id=payload.thread_id)
        return ChatResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat_request_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="RAG agent failed to generate a response") from exc


@router.get("/source/{chunk_id}", response_model=SourceResponse)
async def view_source(chunk_id: str, session: AsyncSession = Depends(get_db_session)) -> SourceResponse:
    """Return full RawMessageChunk payload for a listing source button click."""

    try:
        parsed_id = UUID(chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="chunk_id must be a valid UUID") from exc

    chunk = await session.get(RawMessageChunk, parsed_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Source chunk not found")

    return SourceResponse(
        chunk_id=str(chunk.id),
        message_start=chunk.message_start,
        sender=chunk.sender,
        raw_text=chunk.raw_text,
        cleaned_text=chunk.cleaned_text,
        status=chunk.status,
        created_at=chunk.created_at,
    )
