from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """LangGraph state for the ThreadSense ReAct RAG workflow."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    retrieved_docs: list[Document]
    table_html: str | None
    reasoning: str | None
    sources: list[str]
    thread_id: str
    step_count: int
