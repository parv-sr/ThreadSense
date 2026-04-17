from __future__ import annotations

from functools import lru_cache
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.api.dependencies import get_db_session
from backend.src.api.schemas.chat import ChatRequest, ChatResponse, SourceResponse
from backend.src.core.config import get_settings
from backend.src.embeddings.constants import QDRANT_COLLECTION, QDRANT_VECTOR_NAME
from backend.src.models.ingestion import RawMessageChunk
from backend.src.rag.agent import RAGAgent
from backend.src.rag.retriever import HybridQdrantRetriever

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/chat", tags=["chat"])


def build_rag_agent() -> RAGAgent:
    """Build a production RAG agent using pure dense vectors."""
    logger.info("rag_agent_build_start", qdrant_url=settings.qdrant_endpoint, collection=QDRANT_COLLECTION)

    client: QdrantClient = QdrantClient(url=settings.qdrant_endpoint, api_key=settings.qdrant_api_key)

    vector_store: QdrantVectorStore = QdrantVectorStore(
        client=client,
        collection_name=QDRANT_COLLECTION,
        embedding=OpenAIEmbeddings(model=settings.openai_embedding_model),
        retrieval_mode=RetrievalMode.DENSE,
        vector_name=QDRANT_VECTOR_NAME,
    )

    retriever: HybridQdrantRetriever = HybridQdrantRetriever(vector_store)
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

    agent: RAGAgent = get_agent(request)
    resolved_thread_id: str = payload.thread_id or str(uuid4())

    logger.info("chat_request_received", thread_id=resolved_thread_id)
    try:
        result: dict[str, object] = await agent.invoke(message=payload.message, thread_id=resolved_thread_id)
        return ChatResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.error("agent_failed", thread_id=resolved_thread_id, error=str(exc))
        return ChatResponse(
            thread_id=resolved_thread_id,
            table_html="",
            reasoning="Sorry, I encountered an issue processing your request. Please try again.",
            sources=[],
        )


@router.get("/source/{chunk_id}", response_model=SourceResponse)
async def view_source(chunk_id: str, session: AsyncSession = Depends(get_db_session)) -> SourceResponse:
    """Return full RawMessageChunk payload for a listing source button click."""

    try:
        parsed_id: UUID = UUID(chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="chunk_id must be a valid UUID") from exc

    chunk: RawMessageChunk | None = await session.get(RawMessageChunk, parsed_id)
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
