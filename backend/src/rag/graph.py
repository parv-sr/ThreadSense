from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from qdrant_client.models import Filter

from backend.src.rag.nodes import (
    build_hard_filter_node,
    final_answer_node,
    hybrid_retrieval_node,
    query_parser_node,
    rerank_grader_node,
)
from backend.src.schemas.rag import AnswerWithSources, GradedListing, ParsedQuery


class RAGState(TypedDict):
    """Deterministic RAG graph state used by LangGraph StateGraph."""

    query: str
    parsed_query: ParsedQuery | None
    qdrant_filter: Filter | None
    retrieved_listings: list[Any]
    graded_listings: list[GradedListing]
    final_answer: AnswerWithSources | None
    thread_id: str


# Deterministic pipeline: parse -> hard filter build -> retrieve -> grade -> answer.
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

# MemorySaver enables thread_id-scoped conversation continuity via LangGraph checkpointer.
_checkpointer: MemorySaver = MemorySaver()
rag_app = _graph_builder.compile(checkpointer=_checkpointer)
