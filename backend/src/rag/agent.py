from __future__ import annotations

import uuid

import structlog
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import HumanMessage

from backend.src.rag.graph import RAGGraphBuilder
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.state import AgentState

log = structlog.get_logger(__name__)


class RAGAgent:
    """Main orchestrator for ThreadSense agentic RAG."""

    def __init__(self, retriever: HybridQdrantRetriever) -> None:
        self.memory = ConversationBufferWindowMemory(k=5, return_messages=True)
        self.graph_builder = RAGGraphBuilder(retriever)
        self.graph = self.graph_builder.compile()

    @classmethod
    def compile(cls, retriever: HybridQdrantRetriever) -> "RAGAgent":
        return cls(retriever)

    async def invoke(self, message: str, thread_id: str | None = None) -> dict:
        tid = thread_id or str(uuid.uuid4())
        mem_vars = self.memory.load_memory_variables({})
        history = mem_vars.get("history", [])

        state: AgentState = {
            "thread_id": tid,
            "messages": [*history, HumanMessage(content=message)],
            "retrieved_docs": [],
            "table_html": None,
            "reasoning": None,
            "sources": [],
            "step_count": 0,
        }

        result = await self.graph.ainvoke(state, config={"configurable": {"thread_id": tid}})
        self.memory.save_context({"input": message}, {"output": result.get("reasoning", "")})
        log.info("agent_invoke_done", thread_id=tid, sources=len(result.get("sources", [])))

        return {
            "table_html": result.get("table_html", ""),
            "reasoning": result.get("reasoning", "No answer generated."),
            "sources": result.get("sources", []),
            "thread_id": tid,
        }
