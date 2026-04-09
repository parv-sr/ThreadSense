from __future__ import annotations

import os
from functools import lru_cache
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.api.schemas.chat import ChatRequest, ChatResponse, SourceResponse
from backend.src.models.ingestion import RawMessageChunk
from backend.src.rag.agent import RAGAgent
from backend.src.rag.retriever import HybridQdrantRetriever

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@lru_cache(maxsize=1)
def _get_agent() -> RAGAgent:
    """Create singleton RAG agent backed by hybrid Qdrant retrieval."""

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    collection_name = os.getenv("QDRANT_COLLECTION", "threadsense_listings")
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    qdrant_client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=OpenAIEmbeddings(model=embedding_model),
        sparse_embedding=FastEmbedSparse(model_name="Qdrant/bm25"),
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )
    retriever = HybridQdrantRetriever(vector_store)
    return RAGAgent.compile(retriever)


@router.post("/", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Run one conversational turn through the ReAct RAG graph."""

    try:
        result = await _get_agent().invoke(message=payload.message, thread_id=payload.thread_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat_invoke_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to generate chat response") from exc

    return ChatResponse(**result)


@router.get("/source/{chunk_id}", response_model=SourceResponse)
async def get_source(chunk_id: str, session: AsyncSession = Depends(get_db_session)) -> SourceResponse:
    """Fetch full raw message chunk used by a table row's View Source button."""

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
