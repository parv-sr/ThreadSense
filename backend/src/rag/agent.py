from __future__ import annotations

import uuid

import structlog
from langchain_core.messages import HumanMessage

from backend.src.rag.graph import RAGGraphBuilder
from backend.src.rag.state import AgentState
from backend.src.rag.utils import RAGResponse

logger = structlog.get_logger(__name__)


class RAGAgent:
    """High-level async interface for the ThreadSense ReAct graph."""

    def __init__(self, builder: RAGGraphBuilder) -> None:
        self.builder = builder
        self.graph = builder.compile()

    @classmethod
    def compile(cls, retriever: object) -> "RAGAgent":
        return cls(RAGGraphBuilder(retriever))

    async def invoke(self, message: str, thread_id: str | None = None) -> dict[str, object]:
        """Run one graph turn with checkpointed conversational state."""

        resolved_thread_id = thread_id or str(uuid.uuid4())
        state: AgentState = {
            "thread_id": resolved_thread_id,
            "messages": [HumanMessage(content=message)],
            "retrieved_docs": [],
            "table_html": None,
            "reasoning": None,
            "sources": [],
            "step_count": 0,
        }

        logger.info("rag_agent_invoke", thread_id=resolved_thread_id)
        result = await self.graph.ainvoke(state, config={"configurable": {"thread_id": resolved_thread_id}})

        response = RAGResponse(
            table_html=result.get("table_html") or "",
            reasoning=result.get("reasoning") or "No reasoning generated.",
            sources=result.get("sources") or [],
        )

        return {
            "thread_id": resolved_thread_id,
            "table_html": response.table_html,
            "reasoning": response.reasoning,
            "sources": response.sources,
        }
