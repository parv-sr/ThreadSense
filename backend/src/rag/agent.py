from __future__ import annotations

import uuid

import structlog

from backend.src.rag.graph import rag_app
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.tools import clear_retriever_context, set_retriever_context

logger = structlog.get_logger(__name__)


class RAGAgent:
    """Backward-compatible wrapper around the deterministic LangGraph RAG pipeline."""

    def __init__(self, retriever: HybridQdrantRetriever) -> None:
        # ReAct behavior is deprecated in favor of deterministic StateGraph execution.
        self.retriever: HybridQdrantRetriever = retriever
        self.graph = rag_app

    async def invoke(self, message: str, thread_id: str | None = None) -> dict[str, object]:
        """Invoke deterministic graph; preserved for compatibility with callers that still use RAGAgent."""

        resolved_thread_id: str = thread_id or str(uuid.uuid4())
        set_retriever_context(self.retriever)
        try:
            result: dict[str, object] = await self.graph.ainvoke(
                {"query": message, "thread_id": resolved_thread_id},
                config={"configurable": {"thread_id": resolved_thread_id}},
            )
            final_answer: object | None = result.get("final_answer")
            if final_answer is None:
                return {
                    "thread_id": resolved_thread_id,
                    "table_html": "",
                    "reasoning": "No answer generated.",
                    "sources": [],
                }

            return {
                "thread_id": resolved_thread_id,
                "table_html": str(getattr(final_answer, "table_html", "")),
                "reasoning": str(getattr(final_answer, "answer", "")),
                "sources": list(getattr(final_answer, "sources", [])),
            }
        finally:
            clear_retriever_context()
