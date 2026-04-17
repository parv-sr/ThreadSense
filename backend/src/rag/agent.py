from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
import json
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

from backend.src.rag.graph import ReActRAGGraph
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.tools import clear_retriever_context, set_retriever_context

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

    @staticmethod
    def _extract_retrieved_records(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
        """Parse tool outputs and recover retrieval payloads for final rendering."""

        records: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue

            if message.name not in {"hybrid_retrieve", "filter_listings"}:
                continue

            parsed: Any
            try:
                parsed = json.loads(str(message.content))
            except (TypeError, json.JSONDecodeError):
                continue

            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        records.append(item)

        return records

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
            result: dict[str, Any] = await self.graph.ainvoke(
                {"messages": initial_messages},
                config={
                    "configurable": {"thread_id": resolved_thread_id},
                    "recursion_limit": 6,
                },
            )

            final_messages: Sequence[BaseMessage] = list(result.get("messages", []))
            retrieved_records: list[dict[str, Any]] = self._extract_retrieved_records(final_messages)
            logger.info(
                "agent_retrieved_records_extracted",
                thread_id=resolved_thread_id,
                tool_message_count=len([m for m in final_messages if isinstance(m, ToolMessage)]),
                retrieved_record_count=len(retrieved_records),
            )

            if not retrieved_records:
                logger.warning("agent_retrieved_records_empty", thread_id=resolved_thread_id)

            response_payload: dict[str, object] = await self.react_graph.build_final_response(
                messages=final_messages,
                retrieved_records=retrieved_records,
            )
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
