from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams

from backend.src.api.schemas.chat import ChatRequest, ChatResponse
from backend.src.rag.agent import RAGAgent
from backend.src.rag.retriever import HybridQdrantRetriever

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class _InMemoryEmbedding:
    async def aembed_query(self, text: str) -> list[float]:
        return [float((sum(map(ord, text)) % 97) / 100.0)] * 16


@lru_cache(maxsize=1)
def _get_agent() -> RAGAgent:
    # Placeholder local client setup; in production use env-driven configuration and pre-created collection.
    client = AsyncQdrantClient(location=":memory:")

    async def _ensure_collection() -> None:
        collections = await client.get_collections()
        names = {c.name for c in collections.collections}
        if "threadsense_listings" not in names:
            await client.create_collection(
                collection_name="threadsense_listings",
                vectors_config=VectorParams(size=16, distance=Distance.COSINE),
            )

    # Best-effort startup hook for local/demo mode.
    try:
        import asyncio

        asyncio.get_event_loop().run_until_complete(_ensure_collection())
    except Exception:  # noqa: BLE001
        pass

    from langchain_qdrant import QdrantVectorStore

    store = QdrantVectorStore(
        client=client,
        collection_name="threadsense_listings",
        embedding=_InMemoryEmbedding(),
    )
    retriever = HybridQdrantRetriever(store)
    return RAGAgent.compile(retriever)


@router.post("/", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    agent = _get_agent()
    try:
        result: dict[str, Any] = await agent.invoke(payload.message, payload.thread_id)
        return ChatResponse(**result)
    except Exception as exc:  # noqa: BLE001
        log.exception("chat_endpoint_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Chat agent failed: {exc}") from exc
