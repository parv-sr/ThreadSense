from __future__ import annotations

import uuid

import structlog
from langchain_core.messages import HumanMessage

from backend.src.rag.graph import ReActRAGGraph
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.state import AgentState
from backend.src.rag.tools import clear_retriever_context, set_retriever_context

logger = structlog.get_logger(__name__)


class RAGAgent:
    """ThreadSense async ReAct RAG agent entrypoint."""

    def __init__(self, retriever: HybridQdrantRetriever) -> None:
        self.retriever = retriever
        self.graph = ReActRAGGraph().compile()

    async def invoke(self, message: str, thread_id: str | None = None) -> dict[str, object]:
        """Invoke the graph with persistent thread memory and recursion limit."""

        resolved_thread_id = thread_id or str(uuid.uuid4())
        set_retriever_context(self.retriever)

        try:
            state: AgentState = {
                "thread_id": resolved_thread_id,
                "messages": [HumanMessage(content=message)],
                "retrieved_docs": [],
                "table_html": None,
                "reasoning": None,
                "sources": [],
            }
            logger.info("rag_invoke_start", thread_id=resolved_thread_id)
            result = await self.graph.ainvoke(
                state,
                config={
                    "configurable": {"thread_id": resolved_thread_id},
                    "recursion_limit": 10,
                },
            )
        finally:
            clear_retriever_context()

        logger.info("rag_invoke_done", thread_id=resolved_thread_id, sources=len(result.get("sources", [])))
        return {
            "thread_id": resolved_thread_id,
            "table_html": result.get("table_html", ""),
            "reasoning": result.get("reasoning", "No response generated."),
            "sources": result.get("sources", []),
        }
