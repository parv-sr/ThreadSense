from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent

from backend.src.rag.prompts import REACT_PROMPT, SYSTEM_PROMPT
from backend.src.rag.retriever import HybridQdrantRetriever
from backend.src.rag.state import AgentState
from backend.src.rag.tools import (
    compare_listings,
    filter_listings,
    get_conversation_stats,
    get_listing_details,
    hybrid_retrieve,
    summarize_listings,
)
from backend.src.rag.utils import RAGResponse, render_table_html, validate_citations

log = structlog.get_logger(__name__)


class RAGGraphBuilder:
    """Builds a robust ReAct-style StateGraph for ThreadSense chat."""

    def __init__(self, retriever: HybridQdrantRetriever) -> None:
        self.retriever = retriever
        self.model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.memory = MemorySaver()
        self._base_react = create_react_agent(
            self.model,
            tools=[
                hybrid_retrieve,
                filter_listings,
                compare_listings,
                summarize_listings,
                get_listing_details,
                get_conversation_stats,
            ],
            checkpointer=self.memory,
            prompt=f"{SYSTEM_PROMPT}\n\n{REACT_PROMPT}",
        )

    async def _retrieve_node(self, state: AgentState) -> AgentState:
        step = int(state.get("step_count", 0)) + 1
        query = state["messages"][-1].content if state.get("messages") else ""
        filters = state.get("filters")
        docs = await self.retriever.retrieve(str(query), filters=filters, limit=20)
        log.info("graph_retrieve", thread_id=state.get("thread_id"), docs=len(docs), step=step)
        return {**state, "retrieved_docs": docs, "step_count": step}

    async def _reason_node(self, state: AgentState) -> AgentState:
        docs: list[Document] = state.get("retrieved_docs", [])
        if not docs:
            response = RAGResponse(
                table_html=render_table_html([]),
                reasoning="No relevant listings found in the retrieved dataset.",
                sources=[],
            )
            return {**state, **response.model_dump()}

        rows: list[dict[str, str]] = []
        source_ids: list[str] = []
        for d in docs[:20]:
            meta = d.metadata or {}
            listing_id = str(meta.get("listing_id", meta.get("raw_message_chunk_id", "")))
            if listing_id:
                source_ids.append(listing_id)
            rows.append(
                {
                    "bhk": str(meta.get("bhk", "")),
                    "price": str(meta.get("price", "")),
                    "location": str(meta.get("location", "")),
                    "contact_number": str(meta.get("contact_number", "")),
                    "timestamp": str(meta.get("timestamp", "")),
                    "sender": str(meta.get("sender", "")),
                    "listing_id": listing_id,
                }
            )

        table_html = render_table_html(rows)
        citations = " ".join(f"[source:{sid}]" for sid in source_ids[:8])
        reasoning = (
            f"I found {len(rows)} relevant listings based on your criteria. "
            f"The strongest matches are ranked by retrieval score and metadata alignment. {citations}"
        ).strip()

        ok, missing = validate_citations(reasoning, source_ids)
        if not ok:
            reasoning += f" (citation warning: missing {missing})"

        response = RAGResponse(table_html=table_html, reasoning=reasoning, sources=sorted(set(source_ids)))
        return {**state, **response.model_dump()}

    def _route_after_retrieve(self, state: AgentState) -> str:
        if int(state.get("step_count", 0)) >= 8:
            return "finalize"
        if not state.get("retrieved_docs"):
            return "finalize"
        return "reason"

    async def _finalize_node(self, state: AgentState) -> AgentState:
        table_html = state.get("table_html") or render_table_html([])
        reasoning = state.get("reasoning") or "No answer generated."
        sources = state.get("sources") or []
        final = RAGResponse(table_html=table_html, reasoning=reasoning, sources=sources)
        return {
            **state,
            "table_html": final.table_html,
            "reasoning": final.reasoning,
            "sources": final.sources,
            "messages": [*state.get("messages", []), AIMessage(content=final.reasoning)],
        }

    def compile(self):
        graph = StateGraph(AgentState)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("reason", self._reason_node)
        graph.add_node("finalize", self._finalize_node)
        graph.set_entry_point("retrieve")
        graph.add_conditional_edges(
            "retrieve",
            self._route_after_retrieve,
            {
                "reason": "reason",
                "finalize": "finalize",
            },
        )
        graph.add_edge("reason", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=self.memory)
