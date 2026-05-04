from __future__ import annotations

import asyncio
from typing import Any, TypedDict

import structlog
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from backend.src.core.config import get_settings
from backend.src.rag.nodes import (
    build_hard_filter_node,
    final_answer_node,
    hybrid_retrieval_node,
    query_parser_node,
    rerank_grader_node,
)
from backend.src.schemas.rag import AnswerWithSources, GradedListing, ParsedQuery

settings = get_settings()
log = structlog.get_logger(__name__)


class RAGState(TypedDict):
    """Deterministic RAG graph state used by LangGraph StateGraph."""

    query: str
    parsed_query: ParsedQuery | None
    hard_filters: dict[str, Any]
    retrieved_listings: list[Any]
    graded_listings: list[GradedListing]
    final_answer: AnswerWithSources | None
    thread_id: str


# Build the deterministic pipeline: parse -> filter -> retrieve -> grade -> answer.
_graph_builder: StateGraph[RAGState] = StateGraph(RAGState)
_graph_builder.add_node("parser", query_parser_node)
_graph_builder.add_node("filter_builder", build_hard_filter_node)
_graph_builder.add_node("retrieval", hybrid_retrieval_node)
_graph_builder.add_node("grader", rerank_grader_node)
_graph_builder.add_node("final_answer", final_answer_node)

_graph_builder.add_edge(START, "parser")
_graph_builder.add_edge("parser", "filter_builder")
_graph_builder.add_edge("filter_builder", "retrieval")
_graph_builder.add_edge("retrieval", "grader")
_graph_builder.add_edge("grader", "final_answer")
_graph_builder.add_edge("final_answer", END)

# Redis checkpointer persists thread state across worker processes.
_checkpointer: AsyncRedisSaver | None
try:
    _checkpointer = AsyncRedisSaver(redis_url=settings.redis_broker_url)
    coro = _checkpointer.asetup()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)
except Exception as exc:  # noqa: BLE001
    log.warning("rag_checkpointer_unavailable", error=str(exc))
    _checkpointer = None

rag_app = _graph_builder.compile(checkpointer=_checkpointer)
log.info("rag_graph_ready", checkpointer=_checkpointer is not None)
