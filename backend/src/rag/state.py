from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State carried through the ThreadSense ReAct graph."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    retrieved_docs: list[Document]
    table_html: str | None
    reasoning: str | None
    sources: list[str]
    thread_id: str
