from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.errors import GraphRecursionError

from backend.src.rag.graph import ReActRAGGraph
from backend.src.rag.query_parser import parse_query_constraints
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.tools import clear_retriever_context, get_cached_docs, set_cached_docs, set_retriever_context

logger = structlog.get_logger(__name__)


class RAGAgent:
    """ThreadSense async ReAct RAG agent entrypoint."""

    def __init__(self, retriever: HybridQdrantRetriever) -> None:
        self.retriever: HybridQdrantRetriever = retriever
        self.react_graph: ReActRAGGraph = ReActRAGGraph()
        self.graph = self.react_graph.compile()

    @staticmethod
    def _serialize_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
        """Serialize messages safely for debug logging."""

        serialized: list[dict[str, Any]] = []
        for message in messages:
            if hasattr(message, "model_dump"):
                serialized.append(message.model_dump())
            elif hasattr(message, "dict"):
                serialized.append(message.dict())
            else:
                serialized.append({"type": type(message).__name__, "content": str(getattr(message, "content", ""))})
        return serialized

    async def invoke(self, message: str, thread_id: str | None = None) -> dict[str, object]:
        """Invoke the official ReAct agent with persistent thread memory and recursion limit."""

        resolved_thread_id: str = thread_id or str(uuid.uuid4())
        initial_messages: list[BaseMessage] = [HumanMessage(content=message)]
        set_retriever_context(self.retriever)

        try:
            logger.info(
                "agent_messages_before_llm",
                thread_id=resolved_thread_id,
                messages=self._serialize_messages(initial_messages),
            )
            logger.info("rag_invoke_start", thread_id=resolved_thread_id)
            try:
                result: dict[str, Any] = await self.graph.ainvoke(
                    {"messages": initial_messages},
                    config={
                        "configurable": {"thread_id": resolved_thread_id},
                        "recursion_limit": 12,
                    },
                )

                final_messages: Sequence[BaseMessage] = list(result.get("messages", []))
                cached_docs: list[Document] = list(get_cached_docs())
                if not cached_docs:
                    constraints = parse_query_constraints(message)
                    fallback_docs: list[Document] = await self.retriever.retrieve(
                        query=constraints.normalized_query or message,
                        filters=constraints.filters or None,
                        limit=20,
                    )
                    set_cached_docs(fallback_docs)
                    cached_docs = fallback_docs
                    logger.warning(
                        "rag_docs_cache_miss_recovered",
                        thread_id=resolved_thread_id,
                        recovered_count=len(cached_docs),
                    )

                response_payload = await self.react_graph.build_final_response(
                    final_messages,
                    docs_override=cached_docs,
                )
            except GraphRecursionError as exc:
                logger.warning(
                    "rag_react_recursion_fallback",
                    thread_id=resolved_thread_id,
                    error=str(exc),
                )
                fallback_docs: list[Document] = await self.retriever.retrieve(query=message, filters=None, limit=20)
                set_cached_docs(fallback_docs)
                response_payload = await self.react_graph.build_final_response(initial_messages)
        finally:
            clear_retriever_context()

        logger.info(
            "rag_invoke_done",
            thread_id=resolved_thread_id,
            sources=len(response_payload.get("sources", [])),
        )
        return {
            "thread_id": resolved_thread_id,
            "table_html": response_payload.get("table_html", ""),
            "reasoning": response_payload.get("reasoning", "No response generated."),
            "sources": response_payload.get("sources", []),
        }
